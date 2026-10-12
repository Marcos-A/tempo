# Roadmap

Short-term improvements currently planned for `tempo`.

## Next

### New feature: internship calendar

- [x] Add a separate section to build internship calendars for students.
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
