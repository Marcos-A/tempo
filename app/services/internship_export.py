"""XLSX export for internship calendars.

The workbook has three sheets:

- "Calendari": one Monday-to-Sunday grid per month. Each week uses two rows,
  the dates and the editable hours below them. Week, month and overall totals
  are formulas, so editing any day's hours recalculates everything.
- "Detall": one row per date from the start to the end date. Hours link back to
  the grid and the running and remaining totals are formulas.
- "Configuració": the weekly schedule and the non-teaching periods that were applied.
"""

from __future__ import annotations

import calendar as month_calendar
from datetime import date, timedelta
from io import BytesIO

from openpyxl import Workbook
from openpyxl.comments import Comment
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from app.date_utils import format_display_date, format_month_label
from app.services.hours import MINUTES_PER_HOUR, format_minutes_label
from app.services.internship import (
    DAY_KIND_HOLIDAY,
    DAY_KIND_OVERRIDE,
    DAY_KIND_WEEKEND,
    DAY_KIND_WORKING,
    InternshipCalendar,
)


KIND_FILLS = {
    DAY_KIND_WORKING: "DCEBDD",
    DAY_KIND_HOLIDAY: "F4D6D2",
    DAY_KIND_WEEKEND: "E6E6E6",
    DAY_KIND_OVERRIDE: "F6E2B3",
}
KIND_LABELS = {
    DAY_KIND_WORKING: "Laborable",
    DAY_KIND_HOLIDAY: "Festiu / no lectiu",
    DAY_KIND_WEEKEND: "Sense horari (cap de setmana)",
    DAY_KIND_OVERRIDE: "Dia modificat",
}
OUTSIDE_FONT_COLOR = "A0A69A"
MONTH_TITLE_FILL = PatternFill(fill_type="solid", fgColor="1E3A2D")
HEADER_FILL = PatternFill(fill_type="solid", fgColor="F2ECE0")
THIN_SIDE = Side(style="thin", color="B7BDA8")
THIN_BORDER = Border(left=THIN_SIDE, right=THIN_SIDE, top=THIN_SIDE, bottom=THIN_SIDE)
END_DAY_SIDE = Side(style="medium", color="1E3A2D")
WEEKDAY_SHORT = ("dl.", "dt.", "dc.", "dj.", "dv.", "ds.", "dg.")
GRID_COLUMNS = 8  # Monday..Sunday plus the weekly total.
GRID_COLUMN_WIDTH = 11
METADATA_FIELDS = (
    ("student_name", "Alumne/a"),
    ("training_cycle", "Cicle formatiu"),
    ("group_name", "Grup"),
    ("company_name", "Empresa"),
    ("school_tutor", "Tutor/a del centre"),
    ("school_tutor_email", "Correu del tutor/a del centre"),
    ("company_tutor", "Tutor/a de l'empresa"),
    ("company_tutor_email", "Correu del tutor/a de l'empresa"),
)
GRID_INSTRUCTION = (
    "Modifiqueu les hores de qualsevol dia (fila sota cada data) per recalcular els totals, "
    "les hores restants i la data de fi."
)


def minutes_to_hours(minutes: int) -> int | float:
    """Return an exact hour number: integers stay integers, minutes become fractions."""

    if minutes % MINUTES_PER_HOUR == 0:
        return minutes // MINUTES_PER_HOUR
    return minutes / MINUTES_PER_HOUR


def _hour_format(minutes: int) -> str:
    """Show whole and quarter hours naturally, other minute values with two decimals."""

    return "General" if minutes % 15 == 0 else "0.00"


def _fill(color: str) -> PatternFill:
    return PatternFill(fill_type="solid", fgColor=color)


def _month_starts(start: date, end: date) -> list[date]:
    months: list[date] = []
    current = start.replace(day=1)
    while current <= end:
        months.append(current)
        current = (current.replace(day=28) + timedelta(days=4)).replace(day=1)
    return months


def _label_value_row(sheet, row: int, label: str, value, *, bold_value: bool = False) -> None:
    """Write a 'label: value' line spanning A:C and D:H of the grid sheet."""

    sheet.merge_cells(start_row=row, start_column=1, end_row=row, end_column=3)
    sheet.merge_cells(start_row=row, start_column=4, end_row=row, end_column=GRID_COLUMNS)
    label_cell = sheet.cell(row=row, column=1, value=f"{label}:")
    label_cell.font = Font(bold=True)
    value_cell = sheet.cell(row=row, column=4, value=value)
    value_cell.alignment = Alignment(horizontal="left")
    if bold_value:
        value_cell.font = Font(bold=True)


def build_internship_workbook(
    result: InternshipCalendar,
    *,
    metadata: dict[str, str],
    weekday_minutes: dict[int, int],
    applied_periods: list[dict[str, str]],
) -> BytesIO:
    """Create the internship workbook and return it as an in-memory file.

    `applied_periods` lists the non-working periods that were applied, as
    dictionaries with `start`, `end`, `label` and `source` display strings.
    """

    workbook = Workbook()
    grid = workbook.active
    grid.title = "Calendari"
    detail = workbook.create_sheet("Detall")
    config = workbook.create_sheet("Configuració")

    for column in range(1, GRID_COLUMNS + 1):
        grid.column_dimensions[get_column_letter(column)].width = GRID_COLUMN_WIDTH

    grid.merge_cells(start_row=1, start_column=1, end_row=1, end_column=GRID_COLUMNS)
    title_cell = grid.cell(row=1, column=1, value="Calendari de pràctiques")
    title_cell.font = Font(bold=True, size=14)
    grid.row_dimensions[1].height = 22

    row = 3
    for key, label in METADATA_FIELDS:
        _label_value_row(grid, row, label, (metadata.get(key) or "").strip() or None)
        row += 1

    row += 1
    _label_value_row(grid, row, "Data d'inici", result.start_date)
    grid.cell(row=row, column=4).number_format = "DD/MM/YYYY"
    row += 1
    target_row = row
    _label_value_row(grid, target_row, "Hores totals objectiu", minutes_to_hours(result.target_minutes), bold_value=True)
    grid.cell(row=target_row, column=4).number_format = _hour_format(result.target_minutes)
    row += 1
    planned_row = row
    _label_value_row(grid, planned_row, "Hores planificades", None, bold_value=True)
    row += 1
    remaining_row = row
    _label_value_row(grid, remaining_row, "Hores restants", None, bold_value=True)
    row += 1
    end_row = row
    _label_value_row(grid, end_row, "Data de fi", None, bold_value=True)
    row += 2

    target_ref = f"$D${target_row}"
    planned_ref = f"$D${planned_row}"

    legend_row = row
    grid.cell(row=legend_row, column=1, value="Llegenda:").font = Font(bold=True)
    legend_column = 2
    for kind in (DAY_KIND_WORKING, DAY_KIND_HOLIDAY, DAY_KIND_WEEKEND, DAY_KIND_OVERRIDE):
        grid.merge_cells(start_row=legend_row, start_column=legend_column, end_row=legend_row, end_column=legend_column + 1)
        cell = grid.cell(row=legend_row, column=legend_column, value=KIND_LABELS[kind])
        cell.fill = _fill(KIND_FILLS[kind])
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.font = Font(size=9)
        legend_column += 2
    grid.row_dimensions[legend_row].height = 26
    row += 1
    grid.merge_cells(start_row=row, start_column=1, end_row=row, end_column=GRID_COLUMNS)
    instruction_cell = grid.cell(row=row, column=1, value=GRID_INSTRUCTION)
    instruction_cell.font = Font(italic=True, color="607165", size=9)
    instruction_cell.alignment = Alignment(wrap_text=True, vertical="center")
    grid.row_dimensions[row].height = 26
    row += 2

    days_by_date = {day.date: day for day in result.days}
    hour_cell_by_date: dict[date, str] = {}
    month_total_cells: list[str] = []

    for month_start in _month_starts(result.start_date, result.end_date):
        grid.merge_cells(start_row=row, start_column=1, end_row=row, end_column=GRID_COLUMNS)
        month_cell = grid.cell(row=row, column=1, value=format_month_label(month_start))
        month_cell.font = Font(bold=True, color="FFFFFF")
        month_cell.fill = MONTH_TITLE_FILL
        month_cell.alignment = Alignment(horizontal="center", vertical="center")
        row += 1

        for column, weekday in enumerate(WEEKDAY_SHORT, start=1):
            header = grid.cell(row=row, column=column, value=weekday)
            header.font = Font(bold=True)
            header.fill = HEADER_FILL
            header.alignment = Alignment(horizontal="center")
            header.border = THIN_BORDER
        total_header = grid.cell(row=row, column=GRID_COLUMNS, value="Setmana")
        total_header.font = Font(bold=True)
        total_header.fill = HEADER_FILL
        total_header.alignment = Alignment(horizontal="center")
        total_header.border = THIN_BORDER
        row += 1

        week_total_cells: list[str] = []
        for week in month_calendar.Calendar(firstweekday=0).monthdatescalendar(month_start.year, month_start.month):
            date_row, hours_row = row, row + 1
            for column, current in enumerate(week, start=1):
                if current.month != month_start.month:
                    continue
                date_cell = grid.cell(row=date_row, column=column, value=current)
                date_cell.number_format = "d"
                date_cell.alignment = Alignment(horizontal="right", vertical="top")
                date_cell.font = Font(size=8, color="607165")
                hours_cell = grid.cell(row=hours_row, column=column)
                hours_cell.alignment = Alignment(horizontal="center", vertical="center")
                hours_cell.font = Font(bold=True)
                date_cell.border = Border(left=THIN_SIDE, right=THIN_SIDE, top=THIN_SIDE)
                hours_cell.border = Border(left=THIN_SIDE, right=THIN_SIDE, bottom=THIN_SIDE)

                day = days_by_date.get(current)
                if day is None:
                    date_cell.font = Font(size=8, color=OUTSIDE_FONT_COLOR)
                    continue
                if day.minutes:
                    hours_cell.value = minutes_to_hours(day.minutes)
                    hours_cell.number_format = _hour_format(day.minutes)
                fill = _fill(KIND_FILLS[day.kind])
                date_cell.fill = fill
                hours_cell.fill = fill
                if day.label:
                    date_cell.comment = Comment(day.label, "Tempo")
                if current == result.end_date:
                    date_cell.border = Border(left=END_DAY_SIDE, right=END_DAY_SIDE, top=END_DAY_SIDE)
                    hours_cell.border = Border(left=END_DAY_SIDE, right=END_DAY_SIDE, bottom=END_DAY_SIDE)
                hour_cell_by_date[current] = f"{get_column_letter(column)}{hours_row}"

            # One tall weekly-total cell spanning the date and hours rows.
            grid.merge_cells(start_row=date_row, start_column=GRID_COLUMNS, end_row=hours_row, end_column=GRID_COLUMNS)
            week_total = grid.cell(row=date_row, column=GRID_COLUMNS, value=f"=ROUND(SUM(A{hours_row}:G{hours_row}),2)")
            week_total.alignment = Alignment(horizontal="center", vertical="center")
            # Weeks outside the internship would otherwise show a column of zeros.
            week_total.number_format = "General;-General;;@"
            week_total.font = Font(bold=True)
            week_total.border = THIN_BORDER
            grid.cell(row=hours_row, column=GRID_COLUMNS).border = THIN_BORDER
            week_total_cells.append(f"H{date_row}")
            grid.row_dimensions[date_row].height = 12
            grid.row_dimensions[hours_row].height = 20
            row += 2

        grid.merge_cells(start_row=row, start_column=1, end_row=row, end_column=GRID_COLUMNS - 1)
        month_label = grid.cell(row=row, column=1, value=f"Total {format_month_label(month_start).lower()}")
        month_label.font = Font(bold=True)
        month_label.alignment = Alignment(horizontal="right")
        month_total = grid.cell(row=row, column=GRID_COLUMNS, value=f"=ROUND(SUM({','.join(week_total_cells)}),2)")
        month_total.font = Font(bold=True)
        month_total.alignment = Alignment(horizontal="center")
        month_total.border = THIN_BORDER
        month_total_cells.append(f"H{row}")
        row += 2

    grid.cell(row=planned_row, column=4).value = f"=ROUND(SUM({','.join(month_total_cells)}),2)"
    grid.cell(row=remaining_row, column=4).value = f"=ROUND({target_ref}-{planned_ref},2)"
    for cell_row in (target_row, planned_row, remaining_row):
        grid.cell(row=cell_row, column=4).alignment = Alignment(horizontal="left")

    # Detail sheet: one row per date, linked to the grid's hour cells.
    detail_headers = ("Data", "Dia", "Tipus", "Motiu", "Hores", "Acumulat", "Restants")
    detail.append(detail_headers)
    for cell in detail[1]:
        cell.font = Font(bold=True)
        cell.fill = HEADER_FILL
        cell.border = THIN_BORDER
        cell.alignment = Alignment(horizontal="center")
    detail.freeze_panes = "A2"
    first_detail_row = 2
    # Running totals mix every day's minutes, so they share one format.
    all_quarter_hours = all(day.minutes % 15 == 0 for day in result.days) and result.target_minutes % 15 == 0
    detail_hour_format = "General" if all_quarter_hours else "0.00"
    for index, day in enumerate(result.days):
        detail_row = first_detail_row + index
        hours_ref = f"Calendari!{hour_cell_by_date[day.date]}"
        previous = f"F{detail_row - 1}+" if index else ""
        detail.append(
            [
                day.date,
                WEEKDAY_SHORT[day.date.weekday()],
                KIND_LABELS[day.kind],
                day.label or None,
                f"=IF({hours_ref}=\"\",0,{hours_ref})",
                f"=ROUND({previous}E{detail_row},2)",
                f"=ROUND(Calendari!{target_ref}-F{detail_row},2)",
            ]
        )
        fill = _fill(KIND_FILLS[day.kind])
        for column in range(1, len(detail_headers) + 1):
            cell = detail.cell(row=detail_row, column=column)
            cell.fill = fill
            cell.border = THIN_BORDER
            if column != 4:
                cell.alignment = Alignment(horizontal="center")
        detail.cell(row=detail_row, column=1).number_format = "DD/MM/YYYY"
        for column in (5, 6, 7):
            detail.cell(row=detail_row, column=column).number_format = detail_hour_format
    last_detail_row = first_detail_row + len(result.days) - 1
    total_row = last_detail_row + 1
    detail.cell(row=total_row, column=4, value="Total").font = Font(bold=True)
    detail_total = detail.cell(row=total_row, column=5, value=f"=ROUND(SUM(E{first_detail_row}:E{last_detail_row}),2)")
    detail_total.font = Font(bold=True)
    detail_total.alignment = Alignment(horizontal="center")
    detail.cell(row=total_row + 2, column=1, value="Les hores d'aquest full provenen del full Calendari: modifiqueu-les allà.").font = Font(
        italic=True, color="607165"
    )
    for column, width in zip("ABCDEFG", (12, 6, 26, 32, 9, 10, 10)):
        detail.column_dimensions[column].width = width

    # The end date is the first listed date whose running total reaches the
    # target. MINIFS keeps it live when hours are edited in the grid.
    dates_range = f"Detall!$A${first_detail_row}:$A${last_detail_row}"
    cumulative_range = f"Detall!$F${first_detail_row}:$F${last_detail_row}"
    end_cell = grid.cell(row=end_row, column=4)
    end_cell.value = (
        f"=IF(MAX({cumulative_range})>={target_ref},_xlfn.MINIFS({dates_range},{cumulative_range},\">=\"&{target_ref}),"
        f"\"Encara falten hores\")"
    )
    end_cell.number_format = "DD/MM/YYYY"
    end_cell.alignment = Alignment(horizontal="left")

    grid.page_setup.orientation = "portrait"
    grid.page_setup.fitToWidth = 1
    grid.page_setup.fitToHeight = 0
    grid.sheet_properties.pageSetUpPr.fitToPage = True

    # Configuration sheet: what produced this calendar.
    config.append(["Horari setmanal"])
    config["A1"].font = Font(bold=True)
    for index, weekday in enumerate(("Dilluns", "Dimarts", "Dimecres", "Dijous", "Divendres")):
        minutes = weekday_minutes.get(index, 0)
        config.append([weekday, format_minutes_label(minutes) if minutes else "-"])
    config.append([])
    config.append(["Dies no lectius aplicats"])
    config.cell(row=config.max_row, column=1).font = Font(bold=True)
    config.append(["Inici", "Fi", "Motiu", "Origen"])
    for cell in config[config.max_row]:
        cell.font = Font(bold=True)
        cell.fill = HEADER_FILL
    if applied_periods:
        for period in applied_periods:
            config.append([period["start"], period["end"], period.get("label") or None, period.get("source")])
    else:
        config.append(["-"])
    config.append([])
    config.append(["Generat amb Tempo el", format_display_date(date.today())])
    for column, width in zip("ABCD", (26, 14, 36, 18)):
        config.column_dimensions[column].width = width

    output = BytesIO()
    workbook.save(output)
    output.seek(0)
    return output
