# Tempo Brand Assets

Production package for the approved Tempo mark (Cadence Stack — Production Master). Geometry is frozen: a 20-unit module, 6.5/7-unit optical-corrected gaps, 1.8-unit corner radius, on a 0–100 viewBox. Do not alter coordinates in any file below.

## Directory contents

```
svg/lockup/     symbol + wordmark combined, 7 color variants + 2 reversed-on-field
svg/symbol/     mark only, 7 color variants + 2 reversed-on-field
svg/wordmark/   "tempo" text only, 7 color variants + 2 reversed-on-field
svg/favicon/    favicon.svg (32×32 source)
svg/platform/   app-icon source (pine / deep-pine), maskable source, Safari pinned-tab silhouette
png/symbol/     transparent mark, 5 colors × 15 sizes (16–1024px), rendered natively per size
png/favicon/    favicon-16x16.png, favicon-32x32.png, favicon-48x48.png
png/platform/   full pine app-icon at 15 sizes + apple-touch-icon.png, icon-192.png, icon-512.png, maskable-icon-192/512.png
png/wordmark/   wordmark reference PNGs, pine + white, @1x/@2x
png/lockup/     lockup reference PNGs, standard + reversed, @1x/@2x
ico/            favicon.ico (16/32/48 layers, PNG-in-ICO)
```

## Naming convention

`tempo-<part>-<color>[-reversed][-<size>].<ext>` — `part` is `symbol` / `wordmark` / `lockup` / `icon`. Reversed = white artwork on a solid color field. Platform files that must match exact OS/browser filenames (`favicon.ico`, `apple-touch-icon.png`, `icon-192.png`, etc.) keep those literal names instead.

## Which file to use where

- **Browser tab / bookmark bar:** `svg/favicon/favicon.svg` (primary), `ico/favicon.ico` (fallback for browsers without SVG favicon support).
- **iOS home screen:** `png/platform/apple-touch-icon.png`.
- **Android launcher / Chrome PWA:** `png/platform/icon-192.png`, `icon-512.png`; adaptive/maskable variant `maskable-icon-192.png`, `maskable-icon-512.png`.
- **macOS / Windows / Linux app icon:** `svg/platform/tempo-icon-pine.svg` as source; render platform-native `.icns`/`.ico` from it, or use the matching size in `png/platform/tempo-icon-pine-*.png`.
- **Safari pinned tab:** `svg/platform/safari-pinned-tab.svg` (single-color silhouette, required by Apple's `mask-icon` spec).
- **In-app header / marketing / docs:** `svg/lockup/tempo-lockup-pine.svg` on light surfaces, `tempo-lockup-reversed-pine.svg` on dark or pine surfaces.
- **Symbol alone (app switcher, loading state, watermark):** `svg/symbol/tempo-symbol-pine.svg`, or `-white.svg` on dark backgrounds.

## HTML favicon markup

```html
<link rel="icon" href="/favicon.svg" type="image/svg+xml">
<link rel="icon" href="/favicon.ico" sizes="any">
<link rel="apple-touch-icon" href="/apple-touch-icon.png">
<link rel="mask-icon" href="/safari-pinned-tab.svg" color="#33604c">
```

## PWA manifest reference

```json
{
  "icons": [
    { "src": "/icon-192.png", "sizes": "192x192", "type": "image/png" },
    { "src": "/icon-512.png", "sizes": "512x512", "type": "image/png" },
    { "src": "/maskable-icon-192.png", "sizes": "192x192", "type": "image/png", "purpose": "maskable" },
    { "src": "/maskable-icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "maskable" }
  ]
}
```

## Recommended CSS usage

Prefer the SVG variants inline or via `<img>` — they scale losslessly and inherit no filters/shadows. Use `symbol` SVGs (not `lockup`) as inline UI marks so they don't drag in wordmark whitespace. For a symbol that must sit on an arbitrary/unknown background, use the plain (non-reversed) color that has the most contrast, or `white`/`black` monochrome.

## Transparent vs. reversed variants

- Plain color variants (`pine`, `deep-pine`, `ink`, `black`, `white`) have **transparent backgrounds** — the artwork itself is one solid color, for placing over any surface you control contrast for.
- `-reversed-*` variants include a **filled background** in that color, with white artwork on top — use only when you need the mark pre-composited on its own field (e.g. a colored badge in an email, a slide).
- App-icon / favicon / PWA files always ship as the pine badge + cream mark, matching the shipped in-product icon — do not substitute other color combinations there.

## Known limitation

The wordmark files are **live text** (`<text>`, Inter 600), not outlined paths — this project can't extract font glyph outlines. For an archival/legal master with the type converted to vector paths, open `svg/wordmark/tempo-wordmark-pine.svg` in a vector editor with Inter installed and outline the text there; do not otherwise alter its position or size.

## Do not

- Do not change module width, gap, corner radius, or the symbol's proportions in any file.
- Do not introduce new colors — only the 5 core colors + paper (#eef0ea) / surface (#fbfbf7) supporting tones are approved.
- Do not re-derive icon padding by eye — it's fixed at translate(9,9) scale(0.82) inside a 0–100 viewBox (9% padding), 25%/0.5 scale for maskable safe zones.
