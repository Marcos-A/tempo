"""Tests for the internship calendar: day-by-day calculation, overrides and XLSX export."""

import json
from datetime import date, datetime

import pytest
from fastapi.testclient import TestClient
from openpyxl import load_workbook
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models import AcademicYear, ExcludedPeriod
from app.routes.internship import InternshipRequest, _export_filename
from app.services.internship import (
    DAY_KIND_HOLIDAY,
    DAY_KIND_OVERRIDE,
    DAY_KIND_WEEKEND,
    DAY_KIND_WORKING,
    build_internship_calendar,
)
from app.services.internship_export import METADATA_FIELDS, build_internship_workbook

WEEKDAYS_7H = {0: 420, 1: 420, 2: 420, 3: 420, 4: 420}


def _calendar(target_minutes, weekday_minutes=None, non_working=None, overrides=None, start=date(2026, 10, 12)):
    # 12/10/2026 is a Monday.
    return build_internship_calendar(start, target_minutes, weekday_minutes or WEEKDAYS_7H, non_working or set(), overrides)


def test_end_date_counts_from_start_day_and_skips_weekends():
    """35 h at 7 h/day fills Monday to Friday of the first week."""

    result = _calendar(35 * 60)
    assert result.end_date == date(2026, 10, 16)
    assert result.working_day_count == 5

    result = _calendar(42 * 60)
    # Saturday and Sunday contribute nothing, so the sixth day is the next Monday.
    assert result.end_date == date(2026, 10, 19)
    assert [day.kind for day in result.days[5:7]] == [DAY_KIND_WEEKEND, DAY_KIND_WEEKEND]


def test_holidays_are_skipped():
    holiday = date(2026, 10, 14)
    result = _calendar(35 * 60, non_working={holiday})
    assert result.end_date == date(2026, 10, 19)
    holiday_day = next(day for day in result.days if day.date == holiday)
    assert holiday_day.minutes == 0
    assert holiday_day.kind == DAY_KIND_HOLIDAY


def test_minutes_in_daily_schedule_are_exact():
    """4 h 30 min per day: 9 h ends on the second day without rounding."""

    result = _calendar(9 * 60, weekday_minutes={index: 270 for index in range(5)})
    assert result.end_date == date(2026, 10, 13)
    assert result.scheduled_minutes == 540


def test_last_day_only_gets_remaining_minutes():
    result = _calendar(10 * 60)
    last = result.days[-1]
    assert last.date == date(2026, 10, 13)
    assert last.minutes == 180
    assert last.is_partial
    assert result.scheduled_minutes == 600


def test_override_reducing_hours_moves_end_date_later():
    result = _calendar(35 * 60, overrides={date(2026, 10, 13): 0})
    assert result.end_date == date(2026, 10, 19)
    assert result.days[1].kind == DAY_KIND_OVERRIDE
    assert result.days[1].minutes == 0


def test_override_adding_hours_on_weekend_moves_end_date_earlier():
    base = _calendar(42 * 60)
    assert base.end_date == date(2026, 10, 19)
    result = _calendar(42 * 60, overrides={date(2026, 10, 17): 420})
    assert result.end_date == date(2026, 10, 17)
    saturday = result.days[5]
    assert saturday.kind == DAY_KIND_OVERRIDE and saturday.minutes == 420


def test_override_on_holiday_counts_as_working_time():
    holiday = date(2026, 10, 14)
    result = _calendar(35 * 60, non_working={holiday}, overrides={holiday: 420})
    assert result.end_date == date(2026, 10, 16)


def test_override_matching_default_is_not_flagged():
    result = _calendar(35 * 60, overrides={date(2026, 10, 13): 420})
    assert result.days[1].kind == DAY_KIND_WORKING


def test_zero_schedule_is_rejected():
    with pytest.raises(ValueError):
        _calendar(10 * 60, weekday_minutes={index: 0 for index in range(5)})


def test_schedule_that_never_finishes_is_rejected():
    """Only a few override minutes cannot cover the target: stop at the safety limit."""

    with pytest.raises(ValueError):
        _calendar(100 * 60, weekday_minutes={index: 0 for index in range(5)}, overrides={date(2026, 10, 13): 60})


def _period(period_id, start, end, label):
    return ExcludedPeriod(id=period_id, start_date=start, end_date=end, label=label)


def _payload(**overrides):
    payload = {
        "start_date": "12/10/2026",
        "target_hours": "35",
        "target_minutes": 0,
        "weekday_minutes": {str(index): 420 for index in range(5)},
        "excluded_period_ids": [],
        "extra_periods": [],
        "overrides": {},
        "metadata": {"student_name": "Núria Pérez"},
    }
    payload.update(overrides)
    return payload


def test_request_applies_only_selected_school_periods_and_extra_dates():
    periods = [
        _period(1, date(2026, 10, 13), date(2026, 10, 13), "Festa A"),
        _period(2, date(2026, 10, 14), date(2026, 10, 14), "Festa B"),
    ]
    request = InternshipRequest(
        _payload(excluded_period_ids=[1], extra_periods=[{"start": "15/10/2026", "end": "", "label": "Empresa tancada"}]),
        periods,
    )
    result = request.calculate()
    kinds = {day.date: (day.kind, day.label) for day in result.days}
    assert kinds[date(2026, 10, 13)] == (DAY_KIND_HOLIDAY, "Festa A")
    assert kinds[date(2026, 10, 14)] == (DAY_KIND_WORKING, "")
    assert kinds[date(2026, 10, 15)] == (DAY_KIND_HOLIDAY, "Empresa tancada")
    assert result.end_date == date(2026, 10, 20)
    assert [item["source"] for item in request.applied_periods(result)] == ["Calendari del centre", "Afegit manualment"]


@pytest.mark.parametrize(
    "changes",
    [
        {"weekday_minutes": {"0": 423}},
        {"weekday_minutes": {"0": 13 * 60}},
        {"target_hours": "0"},
        {"overrides": {"not-a-date": 60}},
        {"extra_periods": [{"start": "20/10/2026", "end": "19/10/2026"}]},
    ],
)
def test_request_validation_rejects_bad_input(changes):
    with pytest.raises(ValueError):
        InternshipRequest(_payload(**changes), []).calculate()


def test_target_accepts_minutes():
    request = InternshipRequest(_payload(target_hours="7", target_minutes=30), [])
    result = request.calculate()
    assert request.target_minutes == 450
    assert result.end_date == date(2026, 10, 13)
    assert result.days[-1].minutes == 30


def test_export_filename_is_ascii_slug():
    assert _export_filename({"student_name": "Núria Pérez i Puig"}) == "calendari-practiques-nuria-perez-i-puig.xlsx"
    assert _export_filename({}) == "calendari-practiques.xlsx"


def _export(result, **kwargs):
    workbook_bytes = build_internship_workbook(
        result,
        metadata=kwargs.get("metadata", {"student_name": "Núria", "company_name": "Acme"}),
        weekday_minutes=WEEKDAYS_7H,
        applied_periods=kwargs.get("applied_periods", []),
        non_working_dates=kwargs.get("non_working_dates"),
        labels_by_date=kwargs.get("labels_by_date"),
    )
    return load_workbook(workbook_bytes)


def _find(sheet, value):
    for row in sheet.iter_rows():
        for cell in row:
            cell_value = cell.value.date() if isinstance(cell.value, datetime) else cell.value
            if cell_value == value:
                return cell
    raise AssertionError(f"{value!r} not found")


def _find_day(sheet, value):
    """Find a date in the month grids (formatted as day number), not in the summary block."""

    for row in sheet.iter_rows():
        for cell in row:
            if cell.number_format == "d" and isinstance(cell.value, datetime) and cell.value.date() == value:
                return cell
    raise AssertionError(f"{value!r} not found in grid")


def test_workbook_structure_and_formulas():
    holiday = date(2026, 10, 14)
    result = build_internship_calendar(
        date(2026, 10, 12), 37 * 60 + 30, WEEKDAYS_7H, {holiday}, {date(2026, 10, 17): 150}, {holiday: "Festa local"}
    )
    workbook = _export(result)
    assert workbook.sheetnames == ["Calendari", "Detall", "Configuració"]
    grid = workbook["Calendari"]

    # Metadata and summary values.
    assert grid.cell(row=_find(grid, "Alumne/a:").row, column=4).value == "Núria"
    target_cell = grid.cell(row=_find(grid, "Hores totals objectiu:").row, column=4)
    assert target_cell.value == 37.5
    planned = grid.cell(row=_find(grid, "Hores planificades:").row, column=4).value
    assert planned.startswith("=ROUND(SUM(H")
    remaining = grid.cell(row=_find(grid, "Hores restants:").row, column=4).value
    assert remaining == f"=ROUND($D${target_cell.row}-$D${target_cell.row + 1},2)"
    end_formula = grid.cell(row=_find(grid, "Data de fi:").row, column=4).value
    assert "_xlfn.MINIFS(Detall!" in end_formula

    # Legend lists every colour category.
    for label in ("Dia amb hores", "Sense pràctiques (0 / -)", "Sense horari"):
        _find(grid, label)

    # Each day's hours sit right below its date; non-teaching weekdays show 0 as "-".
    monday = _find_day(grid, date(2026, 10, 12))
    monday_hours = grid.cell(row=monday.row + 1, column=monday.column)
    assert monday_hours.value == 7
    holiday_cell = _find_day(grid, holiday)
    holiday_hours = grid.cell(row=holiday_cell.row + 1, column=holiday_cell.column)
    assert holiday_hours.value == 0
    assert holiday_hours.number_format.endswith(';"-"')
    assert holiday_cell.comment.text.startswith("Festa local")
    saturday = _find_day(grid, date(2026, 10, 17))
    assert grid.cell(row=saturday.row + 1, column=saturday.column).value == 2.5
    assert "Dia modificat" in saturday.comment.text
    # Days without a schedule are grey; the rest are coloured by conditional formatting.
    sunday = _find_day(grid, date(2026, 10, 18))
    assert grid.cell(row=sunday.row + 1, column=sunday.column).value is None
    assert sunday.fill.fgColor.rgb.endswith("E6E6E6")
    assert monday.fill.fill_type is None and saturday.fill.fill_type is None
    day_rules = {
        rule.formula[0]
        for cf in grid.conditional_formatting
        if str(cf.sqref).startswith("A") and len(cf.sqref.ranges) > 1
        for rule in cf.rules
    }
    # Rules are anchored on the first grid week (1 October) and apply across every week.
    first_week = _find_day(grid, date(2026, 10, 1)).row
    assert f"AND(ISNUMBER(A{first_week + 1}),A{first_week + 1}>0)" in day_rules
    assert f'OR(AND(ISNUMBER(A{first_week + 1}),A{first_week + 1}=0),TRIM(A{first_week + 1})="-")' in day_rules

    # Week and month totals are formulas over the hour rows.
    assert grid.cell(row=monday.row, column=8).value == f"=ROUND(SUM(A{monday.row + 1}:G{monday.row + 1}),2)"
    assert f"H{monday.row}:H{monday.row + 1}" in {str(merged) for merged in grid.merged_cells.ranges}
    assert _find(grid, "Total octubre 2026").row > monday.row

    # Detail sheet: hours link to the grid, running and remaining totals are formulas.
    detail = workbook["Detall"]
    assert [cell.value for cell in detail[1]] == ["Data", "Dia", "Tipus", "Motiu", "Hores", "Acumulat", "Restants"]
    hours_ref = f"Calendari!{monday_hours.coordinate}"
    assert detail["E2"].value == f"=IF(ISNUMBER({hours_ref}),{hours_ref},0)"
    assert detail["F2"].value == "=ROUND(E2,2)"
    assert detail["F3"].value == "=ROUND(F2+E3,2)"
    assert detail["G2"].value == f"=ROUND(Calendari!$D${target_cell.row}-F2,2)"
    # The detail runs from the start date to the end of the month after the end date.
    assert detail.cell(row=2 + len(result.days), column=1).value.date() == date(2026, 10, 20)
    assert detail.cell(row=51, column=1).value.date() == date(2026, 11, 30)
    assert detail.cell(row=52, column=4).value == "Total"
    assert detail["C4"].value == "Festiu / no lectiu"
    assert detail["D4"].value == "Festa local"


def test_workbook_extends_to_following_month_for_extra_hours():
    result = _calendar(14 * 60)  # Ends on Tuesday 13/10/2026.
    local_holiday = date(2026, 11, 2)
    workbook = _export(result, non_working_dates={local_holiday}, labels_by_date={local_holiday: "Festa local"})
    grid = workbook["Calendari"]
    _find(grid, "Total novembre 2026")
    with pytest.raises(AssertionError):
        _find(grid, "Total desembre 2026")

    # Days after the end date are editable blanks; non-teaching weekdays show 0.
    after_end = _find_day(grid, date(2026, 10, 14))
    after_end_hours = grid.cell(row=after_end.row + 1, column=after_end.column)
    assert after_end_hours.value is None
    holiday = _find_day(grid, local_holiday)
    assert grid.cell(row=holiday.row + 1, column=holiday.column).value == 0
    assert holiday.comment.text.startswith("Festa local")

    detail = workbook["Detall"]
    tail = _find(detail, local_holiday)
    assert detail.cell(row=tail.row, column=3).value == "Festiu / no lectiu"
    hours_ref = f"Calendari!{after_end_hours.coordinate}"
    assert _find(detail, f"=IF(ISNUMBER({hours_ref}),{hours_ref},0)").row == 4
    end_formula = grid.cell(row=_find(grid, "Data de fi:").row, column=4).value
    assert f"Detall!$A$2:$A${tail.row + 28}" in end_formula  # 2 Nov + 28 days = 30 Nov.


def test_workbook_summary_instructions_and_print_area():
    workbook = _export(_calendar(14 * 60), metadata={"school_tutor_email": "tutor@example.com"})
    grid = workbook["Calendari"]
    assert "school_tutor_email" not in dict(METADATA_FIELDS)
    with pytest.raises(AssertionError):
        _find(grid, "tutor@example.com")

    instructions = _find(grid, "Instruccions")
    assert instructions.column > 8 and instructions.row == 1
    box = grid.cell(row=3, column=instructions.column).value
    assert "4,5" in box and "Hores restants" in box and "posteriors a la data de fi" in box

    target_row = _find(grid, "Hores totals objectiu:").row
    rules = {str(cf.sqref): cf.rules[0] for cf in grid.conditional_formatting}
    planned_rule = rules[f"D{target_row + 1}"]
    assert (planned_rule.operator, planned_rule.formula) == ("lessThan", [f"$D${target_row}"])
    remaining_rule = rules[f"D{target_row + 2}"]
    assert (remaining_rule.operator, remaining_rule.formula) == ("greaterThan", ["0"])
    assert grid.print_area.startswith("'Calendari'!$A$1:$H$")


def test_workbook_grid_hours_add_up_to_target_with_minutes():
    """4 h 30 min days are written as exact fractions, so the grid sums to the target."""

    result = _calendar(37 * 60 + 30, weekday_minutes={index: 270 for index in range(5)})
    grid = _export(result)["Calendari"]
    total = 0.0
    for day in result.days:
        date_cell = _find_day(grid, day.date)
        value = grid.cell(row=date_cell.row + 1, column=date_cell.column).value
        total += value or 0
    assert round(total, 2) == 37.5


@pytest.fixture()
def client():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(bind=engine)
    with TestingSession() as db:
        year = AcademicYear(
            label="2026-27", default_start_date=date(2026, 9, 7), default_end_date=date(2027, 6, 18), is_active=True
        )
        db.add(year)
        db.flush()
        db.add(ExcludedPeriod(academic_year_id=year.id, start_date=date(2026, 10, 13), end_date=date(2026, 10, 13), label="Festa"))
        db.commit()

    def override_db():
        with TestingSession() as session:
            yield session

    app.dependency_overrides[get_db] = override_db
    yield TestClient(app), TestingSession
    app.dependency_overrides.pop(get_db, None)


def test_page_renders_with_nav_and_school_periods(client):
    test_client, _ = client
    response = test_client.get("/practiques")
    assert response.status_code == 200
    assert 'href="/practiques" class="site-nav-link" aria-current="page"' in response.text
    assert "Festa" in response.text
    assert "Planificador d&#39;hores de pràctiques" in response.text
    assert "Correu del tutor/a del centre" not in response.text
    home = test_client.get("/")
    assert 'href="/" class="site-nav-link" aria-current="page"' in home.text
    assert "Planificador curricular" in home.text


def test_calcul_endpoint_returns_days_and_end_date(client):
    test_client, Session = client
    with Session() as db:
        period_id = db.query(ExcludedPeriod).one().id
    response = test_client.post("/practiques/calcul", json=_payload(excluded_period_ids=[period_id]))
    data = response.json()
    assert data["ok"] is True
    assert data["end_date"] == "2026-10-19"
    assert data["days"][1]["kind"] == "holiday"
    assert data["warning"] is None


def test_calcul_endpoint_reports_validation_errors_in_catalan(client):
    test_client, _ = client
    response = test_client.post("/practiques/calcul", json=_payload(start_date="31/02/2026"))
    assert response.status_code == 400
    assert response.json() == {"ok": False, "error": "Introdueix una data en format D/M/AA o D/M/AAAA."}
    response = test_client.post("/practiques/calcul", content=b"not json", headers={"Content-Type": "application/json"})
    assert response.json()["error"] == "Dades de càlcul no vàlides."


def test_calcul_warns_when_running_past_configured_years(client):
    test_client, _ = client
    response = test_client.post("/practiques/calcul", json=_payload(start_date="01/06/2027", target_hours="350"))
    assert "18/06/2027" in response.json()["warning"]


def test_export_endpoint_streams_workbook(client):
    test_client, _ = client
    response = test_client.post("/practiques/export", data={"payload": json.dumps(_payload())})
    assert response.status_code == 200
    assert 'filename="calendari-practiques-nuria-perez.xlsx"' in response.headers["content-disposition"]


def test_export_error_rerenders_page_without_script_injection(client):
    test_client, _ = client
    payload = _payload(target_hours="0", metadata={"student_name": "</script><script>alert(1)</script>"})
    response = test_client.post("/practiques/export", data={"payload": json.dumps(payload)})
    assert response.status_code == 400
    assert "Indica el total" in response.text
    assert "<script>alert(1)</script>" not in response.text
