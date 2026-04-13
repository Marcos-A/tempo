"""XLSX export helpers for the final planning workbook."""

from __future__ import annotations

from io import BytesIO

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from app.services.allocation import RAPlan


WEEKDAY_ABBREVIATIONS = {
    "Dilluns": "dl.",
    "Dimarts": "dt.",
    "Dimecres": "dc.",
    "Dijous": "dj.",
    "Divendres": "dv.",
}

RA_HEADER_FILLS = [
    "E7EFD8",
    "D8EBF2",
    "F7E3D1",
    "E2D8F0",
    "E8E0BC",
    "F6D9E4",
    "D7EEE7",
    "F6E9C9",
    "DDE3F5",
    "F5DCCF",
    "DCECD3",
    "EFE0C8",
]
ROW_START_FILL = PatternFill(fill_type="solid", fgColor="E9E9E9")
THIN_BORDER = Border(
    left=Side(style="thin", color="000000"),
    right=Side(style="thin", color="000000"),
    top=Side(style="thin", color="000000"),
    bottom=Side(style="thin", color="000000"),
)


def _auto_width_for_column_values(values: list[object]) -> float:
    """Return a simple width based on the visible text length."""

    visible_lengths = [len(str(value)) for value in values if value is not None]
    longest = max(visible_lengths, default=0)
    return max(longest + 2, 6)


def _active_ra_keys(row: dict[str, object], ras: list[RAPlan]) -> tuple[str, ...]:
    """Return the ordered RA keys with assigned hours in one calendar row."""

    ra_hours = row["ra_hours"]
    return tuple(ra.key for ra in ras if ra_hours.get(ra.key, 0))


def build_workbook(
    calendar_rows: list[dict[str, object]],
    ras: list[RAPlan],
    summary: dict[str, object],
) -> BytesIO:
    """Create the two-sheet workbook returned to the teacher.

    Zero values in RA cells are written as empty cells so the resulting calendar
    is easier to scan visually.
    """

    workbook = Workbook()
    calendar_sheet = workbook.active
    calendar_sheet.title = "Calendari"

    headers = ["Data", None, "Hores"] + [f"{ra.name}: {ra.hours} h" for ra in ras]
    calendar_sheet.append(headers)
    calendar_sheet.merge_cells("A1:B1")
    calendar_sheet["A1"].alignment = Alignment(horizontal="left", vertical="center")
    for cell in calendar_sheet[1]:
        cell.font = Font(bold=True)
    for index, _ra in enumerate(ras):
        calendar_sheet.cell(row=1, column=4 + index).fill = PatternFill(
            fill_type="solid",
            fgColor=RA_HEADER_FILLS[index],
        )
    calendar_sheet.freeze_panes = "A2"

    previous_active_keys: tuple[str, ...] | None = None
    for row in calendar_rows:
        # The weekday is exported as a short label because the sheet is meant to
        # be practical for teachers, not just machine-readable.
        excel_row = [WEEKDAY_ABBREVIATIONS.get(row["weekday"], row["weekday"]), row["date"], row["total_hours"]]
        ra_hours = row["ra_hours"]
        excel_row.extend(ra_hours[ra.key] or None for ra in ras)
        calendar_sheet.append(excel_row)
        active_keys = _active_ra_keys(row, ras)
        if previous_active_keys is not None and active_keys != previous_active_keys:
            for cell in calendar_sheet[calendar_sheet.max_row]:
                cell.fill = ROW_START_FILL
        previous_active_keys = active_keys

    for row in calendar_sheet.iter_rows(min_row=2, min_col=2, max_col=2):
        row[0].number_format = "DD/MM/YYYY"

    weekday_values = [calendar_sheet[f"A{row_index}"].value for row_index in range(2, calendar_sheet.max_row + 1)]
    date_values = [calendar_sheet[f"B{row_index}"].value.strftime("%d/%m/%Y") for row_index in range(2, calendar_sheet.max_row + 1)]
    hour_values = [calendar_sheet[f"C{row_index}"].value for row_index in range(1, calendar_sheet.max_row + 1)]
    calendar_sheet.column_dimensions["A"].width = _auto_width_for_column_values(weekday_values)
    calendar_sheet.column_dimensions["B"].width = _auto_width_for_column_values(date_values)
    calendar_sheet.column_dimensions["C"].width = _auto_width_for_column_values(hour_values)
    for row in calendar_sheet.iter_rows(min_row=2, max_row=calendar_sheet.max_row, min_col=1, max_col=2):
        for cell in row:
            cell.alignment = Alignment(horizontal="center", vertical="center")
    for row in calendar_sheet.iter_rows(min_row=1, max_row=calendar_sheet.max_row, min_col=3, max_col=3):
        row[0].alignment = Alignment(horizontal="center", vertical="center")
    for index in range(len(ras)):
        column_letter = get_column_letter(4 + index)
        calendar_sheet.column_dimensions[column_letter].width = 14
        for row in calendar_sheet.iter_rows(min_row=1, max_row=calendar_sheet.max_row, min_col=4 + index, max_col=4 + index):
            row[0].alignment = Alignment(horizontal="center", vertical="center")

    for row in calendar_sheet.iter_rows(min_row=1, max_row=calendar_sheet.max_row, min_col=1, max_col=3 + len(ras)):
        for cell in row:
            cell.border = THIN_BORDER

    summary_sheet = workbook.create_sheet("Resum")
    summary_sheet.freeze_panes = "A2"
    summary_sheet.append(["Camp", "Valor"])
    for cell in summary_sheet[1]:
        cell.font = Font(bold=True)

    for key, value in summary.items():
        summary_sheet.append([key, value])

    summary_sheet.column_dimensions["A"].width = 28
    summary_sheet.column_dimensions["B"].width = 40

    output = BytesIO()
    workbook.save(output)
    output.seek(0)
    return output
