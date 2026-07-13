# Tempo — final logo assets

**Mark:** segmented "T" — a continuous stem crossed by three discrete interval
blocks, doubling as the app's initial and as the "structured time blocks"
idea the product is built on.

## Files

| File | Description |
|---|---|
| `tempo-mark-pine.svg` | Mark alone, pine green (`#33604c`) — primary use |
| `tempo-mark-cream-on-transparent.svg` | Mark alone, cream fill — for dark/pine backgrounds |
| `tempo-mark-mono-dark.svg` | Mark alone, near-black — strict monochrome, light bg |
| `tempo-mark-mono-light.svg` | Mark alone, cream — strict monochrome, dark bg |
| `tempo-app-icon.svg` | 512x512 rounded-square app icon (pine bg, cream mark) |
| `tempo-favicon.svg` | 32x32 favicon (simplified corner radius, verified legible at 16px) |
| `tempo-wordmark-pine.svg` | "tempo" wordmark, pine green, no mark |
| `tempo-wordmark-ink.svg` | "tempo" wordmark, near-black |
| `tempo-wordmark-cream.svg` | "tempo" wordmark, cream, for dark backgrounds |
| `tempo-lockup-light-bg.svg` | Badge + wordmark, for light backgrounds (nav bars, headers) |
| `tempo-lockup-dark-bg.svg` | Badge + wordmark, for dark/pine backgrounds |

Assets live in `app/static/img/`, served at `/static/img/<file>`.

## Usage

- App icon / favicon / collapsed UI → `tempo-app-icon.svg` / `tempo-favicon.svg`
- Nav bar, product header, docs → `tempo-lockup-light-bg.svg` (or `-dark-bg` on pine)
- Legal text, email signature, plain text → wordmark files only, no mark
- Wordmark set in Inter, weight 600, tight negative letter-spacing

## Color reference

| Role | Hex |
|---|---|
| Pine (primary) | `#33604c` |
| Dark pine (alt) | `#1e3a2d` |
| Ochre (optional accent, sparing use only) | `#8a5a2b` |
| Background (light) | `#eef0ea` / `#fbfbf7` |
