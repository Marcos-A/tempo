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

### Branding

- [ ] Give the Tempo logo and wordmark a more polished look with a subtle relief, bevel or 3D effect.
  - **Goal:** discreet, professional and clean, but less flat and simple than the current branding.
  - **Keep the identity:** keep the "cadence stack" construction (repeating rectangular modules, Pine color, rounded corners) described in Section 4 of `design/tempo-design-system.md`. Refine it; don't replace it.
  - **Directions to explore:**
    - Light bevel on each module: a lighter top/left edge and a darker bottom/right edge, using tints and shades of Pine.
    - Faceted or chamfered geometric modules (for example angled corners or a split-tone face) for a more crafted, geometric feel.
    - Soft depth: a very slight offset shadow or a two-tone extrusion, with no glossy or skeuomorphic effects.
    - A matching treatment for the wordmark, such as a subtle inner shadow or a two-tone fill, that stays readable in Inter 600.
  - **Constraints:**
    - Pure SVG (gradients and paths only, no raster effects or filters that render inconsistently).
    - Readable down to 16px: keep a flat build for the favicon and small sizes if the effect gets muddy.
    - Provide light, reversed/white (dark mode) and monochrome variants.
  - **Deliverables:**
    - Prepare 2–3 mockups of the symbol, lockup and app icon so one direction can be chosen.
    - Then update the SVGs in `app/static/img/` and `design/brand/` (svg, png, ico) and the logo section of the design system document.
  - Done when: the chosen design replaces the current assets in the header, favicon and app icon, and looks right in light mode, dark mode and at 16px.

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
