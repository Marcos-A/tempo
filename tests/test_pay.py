import json
import re
from datetime import date, timedelta
from fractions import Fraction
from io import BytesIO
from types import SimpleNamespace

import pytest
from openpyxl import load_workbook
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import AcademicYear, AppSetting
from app.routes import admin as admin_routes
from app.routes.internship import InternshipRequest
from app.services.pay import estimate_pay, format_euros, get_smi_cents, parse_euros, set_smi_cents
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
    assert intensive.pay_details() == [("Grau", "Grau superior"), ("SMI mensual", "1.184,00 €")]
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
    assert "<dt>Grau</dt><dd>Grau mitjà</dd>" in html and "<dt>SMI mensual</dt><dd>1.184,00 €</dd>" in html
    plan = json.loads(html.split('id="tempo-internship-plan">')[1].split("</script>")[0])["plan"]
    assert (plan["grade"], plan["smi"]) == ("mitja", "1184")

    workbook = load_workbook(BytesIO(test_client.post("/practiques/export", data={"payload": json.dumps(payload)}).content))
    labels = {row[0].value: row[3].value for row in workbook["Calendari"].iter_rows(min_row=3, max_row=15)}
    assert labels["Grau:"] == "Grau mitjà" and labels["SMI mensual:"] == "1.184,00 €"


def _worked_days(*months):
    """8 h days for each (first date, hours) pair, one a day from that date."""

    return [
        SimpleNamespace(date=first + timedelta(days=index), minutes=480)
        for first, hours in months
        for index in range(hours // 8)
    ]


SMI_2026 = 122100  # 1.221,00 € × 14 = 17.094 €, the Coordinator's example.


def test_estimate_follows_the_coordinators_example():
    estimate = estimate_pay(_worked_days((date(2026, 9, 1), 160)), 320 * 60, "superior", SMI_2026)
    assert estimate.hourly_cents == Fraction(1709400, 12 * 20 * 8) == Fraction(890.3125)
    assert estimate.month_cents == {"2026-09": 85470}  # 160 h × 8,903125 € × 60 %
    assert estimate.month_labels == {"2026-09": "≈ 854,70 € · 60 %"}
    assert "1.221,00 € × 14 pagues ÷ 12 mesos ÷ 20 dies ÷ 8 h = 8,90 €/h" in estimate.note
    assert "60 % (5,34 €/h) fins a les 160 h i 70 % (6,23 €/h)" in estimate.note


def test_grau_mitja_earns_half_for_all_the_hours():
    estimate = estimate_pay(_worked_days((date(2026, 9, 1), 160), (date(2026, 10, 1), 160)), 320 * 60, "mitja", SMI_2026)
    assert estimate.month_cents == {"2026-09": 71225, "2026-10": 71225}
    assert estimate.month_labels["2026-10"] == "≈ 712,25 € · 50 %"
    assert "50 % (4,45 €/h) per a totes les hores" in estimate.note


def test_grau_superior_changes_rate_at_half_of_the_total_hours():
    days = _worked_days((date(2026, 9, 1), 96), (date(2026, 10, 1), 128), (date(2026, 11, 1), 96))
    estimate = estimate_pay(days, 320 * 60, "superior", SMI_2026)
    # October: 64 h at 60 % and 64 h at 70 %.
    assert estimate.month_cents == {"2026-09": 51282, "2026-10": 74074, "2026-11": 59829}
    assert estimate.month_labels["2026-09"].endswith("· 60 %")
    assert estimate.month_labels["2026-10"].endswith("· 60 % i 70 %")
    assert estimate.month_labels["2026-11"].endswith("· 70 %")
    assert estimate.total_cents == 51282 + 74074 + 59829


def test_half_of_the_hours_is_half_of_the_agreement_even_if_the_plan_stops_short():
    estimate = estimate_pay(_worked_days((date(2026, 9, 1), 160)), 400 * 60, "superior", SMI_2026)
    assert estimate.month_labels["2026-09"].endswith("· 60 %")


def test_days_without_hours_add_no_month():
    days = [SimpleNamespace(date=date(2026, 8, 31), minutes=0), *_worked_days((date(2026, 9, 1), 8))]
    assert list(estimate_pay(days, 8 * 60, "mitja", SMI_2026).month_cents) == ["2026-09"]


def test_notice_appears_only_when_the_hours_reach_a_later_year():
    same_year = estimate_pay(_worked_days((date(2026, 9, 1), 80)), 80 * 60, "mitja", SMI_2026)
    assert same_year.smi_notice == ""
    starts_in_january = estimate_pay(_worked_days((date(2027, 1, 11), 80)), 80 * 60, "mitja", SMI_2026)
    assert starts_in_january.smi_notice == ""
    crossing = estimate_pay(_worked_days((date(2026, 12, 1), 80), (date(2027, 1, 11), 80)), 160 * 60, "mitja", SMI_2026)
    assert "any nou" in crossing.smi_notice and "arriba al 2027" in crossing.smi_notice
    # Still calculated for January, with the same SMI.
    assert crossing.month_cents["2027-01"] == crossing.month_cents["2026-12"]
    no_hours_there = [*_worked_days((date(2026, 12, 1), 80)), SimpleNamespace(date=date(2027, 1, 4), minutes=0)]
    assert estimate_pay(no_hours_there, 80 * 60, "mitja", SMI_2026).smi_notice == ""


def _intensive_plan(**overrides):
    # Tuesday: 16 h in September, then 64 h in October, 24 h of them below the half.
    return _payload(
        modality="intensiva",
        grade="superior",
        smi="1221",
        start_date="29/09/2026",
        target_hours="80",
        weekday_minutes={str(index): 480 for index in range(5)},
        **overrides,
    )


def test_calculation_returns_the_estimate_only_with_an_smi(client):  # noqa: F811
    test_client, _ = client
    pay = test_client.post("/practiques/calcul", json=_intensive_plan()).json()["pay"]
    assert pay["total"] == "462,96 €"
    assert pay["months"] == {"2026-09": "≈ 85,47 € · 60 %", "2026-10": "≈ 377,49 € · 60 % i 70 %"}
    assert pay["smi_notice"] == ""
    without_smi = {**_intensive_plan(), "smi": ""}
    assert test_client.post("/practiques/calcul", json=without_smi).json()["pay"] is None
    assert test_client.post("/practiques/calcul", json=_payload(smi="1221")).json()["pay"] is None


def test_read_only_copies_show_the_estimate_and_the_notice(client):  # noqa: F811
    test_client, _ = client
    html = test_client.post("/practiques/export-html", data={"payload": json.dumps(_intensive_plan())}).text
    assert "462,96 €" in html and "≈ 377,49 € · 60 % i 70 %" in html
    assert 'class="warning-box internship-pay-notice"' not in html
    crossing = {**_intensive_plan(), "start_date": "28/12/2026"}
    html = test_client.post("/practiques/export-html", data={"payload": json.dumps(crossing)}).text
    assert 'class="warning-box internship-pay-notice"' in html and "arriba al 2027" in html
    general = test_client.post("/practiques/export-html", data={"payload": json.dumps(_payload())}).text
    assert 'class="internship-pay"' not in general


def test_workbook_formulas_give_the_same_amounts(client):  # noqa: F811
    test_client, _ = client
    content = test_client.post("/practiques/export", data={"payload": json.dumps(_intensive_plan())}).content
    grid = load_workbook(BytesIO(content))["Calendari"]

    # Spreadsheet times for what the grid adds up: 16 h, then 64 h, then nothing.
    month_rows = [row[0].row for row in grid.iter_rows(min_col=1, max_col=1) if str(row[0].value or "").startswith("Total ")]
    values = {f"H{row}": hours / 24 for row, hours in zip(month_rows, [16, 64] + [0] * len(month_rows))}
    labels = {row[0].value: row[0].row for row in grid.iter_rows(min_row=3, max_row=25, max_col=1) if row[0].value}
    values[f"$D${labels['Hores totals objectiu:']}"] = 80 / 24

    def evaluate(formula: str) -> float:
        names = {"SUM": lambda *items: sum(items), "MIN": min, "ROUND": round}
        return eval(re.sub(r"\$?[A-Z]\$?\d+", lambda ref: repr(values[ref.group()]), formula[1:]), names)  # noqa: S307

    pay_cells = [cell for row in grid.iter_rows(min_col=8, max_col=8) for cell in row if str(cell.value).startswith("=ROUND(24*")]
    assert [evaluate(cell.value) for cell in pay_cells][:2] == [85.47, 377.49]
    assert grid.cell(row=pay_cells[0].row, column=1).value == "Retribució estimada"
    for cell in pay_cells:
        values[cell.coordinate] = evaluate(cell.value)

    total = grid.cell(row=labels["Retribució estimada:"], column=4)
    assert round(evaluate(total.value), 2) == 462.96
    assert any("8,90 €/h" in str(row[0].value) for row in grid.iter_rows(max_row=25, max_col=1))
