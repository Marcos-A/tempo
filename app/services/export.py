"""XLSX export helpers for the final planning workbook."""

from __future__ import annotations

from io import BytesIO

from openpyxl import Workbook
from openpyxl.styles import Font

from app.services.allocation import RAPlan


WEEKDAY_ABBREVIATIONS = {
    "Dilluns": "dl.",
    "Dimarts": "dt.",
    "Dimecres": "dc.",
    "Dijous": "dj.",
    "Divendres": "dv.",
}


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

    headers = ["Dia setmana", "Data", "Hores totals"] + [ra.name for ra in ras]
    calendar_sheet.append(headers)
    for cell in calendar_sheet[1]:
        cell.font = Font(bold=True)
    calendar_sheet.freeze_panes = "A2"

    for row in calendar_rows:
        # The weekday is exported as a short label because the sheet is meant to
        # be practical for teachers, not just machine-readable.
        excel_row = [WEEKDAY_ABBREVIATIONS.get(row["weekday"], row["weekday"]), row["date"], row["total_hours"]]
        ra_hours = row["ra_hours"]
        excel_row.extend(ra_hours[ra.key] or None for ra in ras)
        calendar_sheet.append(excel_row)

    for row in calendar_sheet.iter_rows(min_row=2, min_col=2, max_col=2):
        row[0].number_format = "YYYY-MM-DD"

    for column in ["A", "B", "C"]:
        calendar_sheet.column_dimensions[column].width = 16
    for index in range(len(ras)):
        calendar_sheet.column_dimensions[chr(ord("D") + index)].width = 14

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
