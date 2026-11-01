import json
from datetime import date
from io import BytesIO

import pytest
from openpyxl import load_workbook
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import AcademicYear, AppSetting
from app.routes import admin as admin_routes
from app.routes.internship import InternshipRequest
from app.services.pay import format_euros, get_smi_cents, parse_euros, set_smi_cents
from tests.test_academic_year_admin import _legacy_engine, _request
from tests.test_internship import _payload, client  # noqa: F401  (pytest fixture)


@pytest.mark.parametrize(
    ("raw", "cents"),
    [("1.184,00", 118400), ("1184,5", 118450), ("1184", 118400), ("1184.50", 118450), ("1.184", 118400), (" 1 184,00 € ", 118400)],
)
def test_parse_euros_reads_catalan_and_plain_amounts(raw, cents):
    assert parse_euros(raw) == cents


@pytest.mark.parametrize("raw", ["", "abc", "1,234,5", "0", "1184,555", "100000,01"])
def test_parse_euros_rejects_invalid_amounts(raw):
    with pytest.raises(ValueError):
        parse_euros(raw)


def test_format_euros_groups_thousands():
    assert format_euros(118400) == "1.184,00"
    assert format_euros(5) == "0,05"


def test_admin_sets_and_clears_the_smi(tmp_path):
    engine = _legacy_engine(tmp_path / "planner.db")
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
    with SessionLocal() as session:
        year = AcademicYear(label="2026-27", default_start_date=date(2026, 9, 1), default_end_date=date(2027, 6, 30), is_active=True)
        session.add(year)
        session.commit()

        response = admin_routes.update_smi(_request("/admin/smi"), " 1.184,00 ", str(year.id), session, object())
        assert response.headers["location"] == f"/admin?year_id={year.id}&status=smi-updated#internship-smi"
        assert get_smi_cents(session) == 118400

        invalid = admin_routes.update_smi(_request("/admin/smi"), "mil", str(year.id), session, object())
        assert invalid.status_code == 400 and "SMI" in invalid.context["error"]
        assert invalid.context["smi"] == "1.184,00"
        assert get_smi_cents(session) == 118400

        cleared = admin_routes.update_smi(_request("/admin/smi"), "", str(year.id), session, object())
        assert cleared.headers["location"].endswith("status=smi-cleared#internship-smi")
        assert get_smi_cents(session) is None
        assert session.scalar(select(AppSetting)).value is None


def test_planner_offers_the_admins_smi(client):  # noqa: F811
    test_client, Session = client
    assert 'const ADMIN_SMI = "";' in test_client.get("/practiques").text
    with Session() as db:
        set_smi_cents(db, 118400)
    assert 'const ADMIN_SMI = "1.184,00";' in test_client.get("/practiques").text


def test_request_reads_grade_and_smi_only_in_the_intensive_modality():
    intensive = InternshipRequest(_payload(modality="intensiva", grade="superior", smi="1.184,00"), [])
    assert (intensive.grade, intensive.smi_cents) == ("superior", 118400)
    assert intensive.pay_details() == [("Grau", "Grau superior"), ("SMI", "1.184,00 €")]
    assert InternshipRequest(_payload(modality="intensiva"), []).grade == "mitja"
    general = InternshipRequest(_payload(grade="nope", smi="nope"), [])
    assert (general.grade, general.smi_cents, general.pay_details()) == ("", None, [])
    with pytest.raises(ValueError, match="Grau"):
        InternshipRequest(_payload(modality="intensiva", grade="alt"), [])
    with pytest.raises(ValueError, match="SMI"):
        InternshipRequest(_payload(modality="intensiva", smi="mil"), [])


def test_exports_show_grade_and_smi_in_the_header(client):  # noqa: F811
    test_client, _ = client
    payload = _payload(modality="intensiva", grade="mitja", smi="1184")
    html = test_client.post("/practiques/export-html", data={"payload": json.dumps(payload)}).text
    assert "<dt>Grau</dt><dd>Grau mitjà</dd>" in html and "<dt>SMI</dt><dd>1.184,00 €</dd>" in html
    plan = json.loads(html.split('id="tempo-internship-plan">')[1].split("</script>")[0])["plan"]
    assert (plan["grade"], plan["smi"]) == ("mitja", "1184")

    workbook = load_workbook(BytesIO(test_client.post("/practiques/export", data={"payload": json.dumps(payload)}).content))
    labels = {row[0].value: row[3].value for row in workbook["Calendari"].iter_rows(min_row=3, max_row=15)}
    assert labels["Grau:"] == "Grau mitjà" and labels["SMI:"] == "1.184,00 €"
