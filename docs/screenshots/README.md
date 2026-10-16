# Screenshots

This folder is reserved for screenshots used in repository documentation.

## Purpose

Keep README visuals separated from product assets so branding files, UI screenshots, and implementation files do not get mixed together.

## Current Set

The files in this folder document the two public tools. For the curriculum planner, the README deliberately uses the usual sequential path and one example of the advanced parallel mode; for the internship hours planner, it uses the three `tempo-practiques-*` captures.

| File | Workflow point | README use |
| --- | --- | --- |
| `tempo-step-1-landing_page.png` | Public entry screen | Linked as a supplementary view |
| `tempo-step-1-sequencial.png` | Step 1: module setup in sequential mode | Main visual walkthrough |
| `tempo-step-2-sequencial.png` | Step 2: allocate available hours and prepare export | Main visual walkthrough |
| `tempo-step-3-spreadsheet_1.png` | Result: primary view of the generated XLSX workbook | Main visual walkthrough |
| `tempo-step-1-parallel.png` | Step 1: configure two parallel blocks | Supporting advanced-mode example |
| `tempo-step-2-parallel.png` | Step 2: distribute RAs across parallel blocks | Supporting advanced-mode example |
| `tempo-step-3-spreadsheet_2.png` | Result: secondary workbook view | Kept for detailed documentation |
| `tempo-practiques-step-1-formulari.png` | Internship planner: a saved calendar just opened with «Obre un calendari desat» (start date, total hours and a weekly schedule split into two periods) | Internship walkthrough |
| `tempo-practiques-step-2-calendari.png` | Internship planner: days without internship, the resulting calendar, the XLSX, HTML and PDF download buttons and the note on reopening the HTML | Internship walkthrough |
| `tempo-practiques-step-3-editor-dia.png` | Internship planner: changing the hours of a range of days picked with Shift+click | Internship walkthrough |

`step-3` describes the exported result, not a third screen in the application: the teacher interface itself has two steps.

## Naming

The current names are stable and intentionally group assets by workflow state. For future captures, keep the `tempo-step-<number>-<description>.png` pattern (prefixed with the tool, e.g. `tempo-practiques-step-<number>-<description>.png`, for the internship planner) and use the existing spelling (`sequencial`) for continuity.

## Format Guidelines

- Prefer `png` for interface screenshots.
- Use `webp` only if GitHub rendering and visual clarity are both acceptable.
- Export clean captures without browser extensions, private data, or local debug noise.
- Keep one screenshot per major flow instead of many near-duplicates.

## Maintenance

- Replace outdated screenshots when the interface changes materially.
- Keep links in `README.md` and `README.en.md` aligned with the actual filenames stored here.
- If annotated screenshots are needed, store the annotated version next to the clean source with a clear suffix such as `-annotated`.
