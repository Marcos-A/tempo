# Roadmap

Short-term improvements currently planned for `tempo`.

## Next

### XLSX export

- [ ] Wrap text in cells that hold RA names so long names don't make columns too wide.
  - Apply `wrap_text=True` (with vertical alignment) to the cells holding RA names in `app/services/export.py`, including the optional RA name row under the RA key headers.
  - Keep RA columns at a fixed, reasonable width (e.g. `RA_COLUMN_WIDTH`) instead of growing them to fit the name.
  - Raise the row height so wrapped names show in full (estimate it from the longest name, like the instruction banner does), since openpyxl doesn't auto-fit row heights.
  - Done when: an export with long RA names opens in Excel and LibreOffice with narrow RA columns and every name fully readable on several lines.

### UI and localization

- [ ] Translate the "Block 1" / "Block 2" labels in parallel-block mode to Catalan ("Bloc 1" / "Bloc 2").
  - The pill in `app/templates/teacher/distribution.html` renders the internal key (`block.key|replace("_", " ")`). Show `block.name`, or a Catalan label, instead of the raw key.
  - Check the rest of the parallel-block UI (summary, sticky pending-hours box, drop zones, JS-generated text) for any other English block labels.
  - Done when: no "Block" text is visible anywhere in parallel-block mode.

- [ ] Show a discreet calendar picker when a date input is clicked.
  - Cover every date field in the teacher and admin forms (course dates, excluded dates, holidays, etc.).
  - Prefer native `<input type="date">` if it fits the current date format. Otherwise use a small, lightweight picker that matches the app's style.
  - Keep typing dates by hand possible, keep the existing date format and validation, and use Catalan locale (Monday as first day of the week, Catalan month and day names).
  - Done when: clicking any date field opens a compact calendar, picking a day fills the field in the expected format, and typing by hand still works.

### New feature: internship calendar

- [ ] Add a separate section to build internship calendars for students.
  - **Entry point:** a new section or page that is independent from the RA-distribution workflow, with its own navigation entry.
  - **Inputs:**
    - Start date.
    - Total number of hours to complete.
    - Default hours per working day (possibly per weekday).
    - Non-working dates: reuse the existing academic-year holidays and excluded dates where possible, and allow extra ones.
  - **Calculation:** go day by day from the start date, adding the default daily hours on working days and skipping weekends and holidays, until the total is reached. The last day may get only the remaining hours. Show the computed end date.
  - **Per-day overrides:** let the user change the hours assigned to any date (including setting it to 0 or adding hours on a normally non-working day). The calendar then recalculates the following days and the end date.
  - **Preview:** show the calendar in the UI before exporting, with working and holiday dates clearly distinguished.
  - **XLSX export:**
    - Calendar layout with distinct colors for working days, holidays/non-working days and overridden days.
    - Hours per day, running total and overall total vs. target hours.
    - Use formulas (like the existing calendar export) so that editing a day's hours in the spreadsheet recalculates the running totals and remaining hours.
    - Add a short legend for the colors.
  - **Tests:** cover the end-date calculation, holiday skipping, partial last day, overrides that move the end date earlier or later, and the XLSX structure.
  - Done when: a user can enter a start date and total hours, adjust individual days, see the end date update, and download a colored spreadsheet whose totals recalculate when edited.
