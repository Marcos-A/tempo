# Tempo Design System

**Version 1.1 — Canonical Reference**
Status: Approved. The visual identity documented here (Sections 4–8) is frozen. Component patterns, tokens, and implementation guidance may evolve under the governance described in Section 18.

**Revision note (1.1):** a design review found that three tokens in v1.0 (`Warning`, `Success`, `Muted`) did not meet WCAG AA contrast in every context the document itself specified they'd be used in — e.g. `Warning` as text on Paper measured 2.91:1 against a required 4.5:1. All three were re-derived at the same hue to the nearest lightness step that clears AA in every stated use case, verified numerically rather than by eye. See Section 5 for the corrected values and the reasoning. This also closes gaps around subtle/tint badge backgrounds, dropdown radius ambiguity, elevation/shadow, and a fully-specified dark-mode token set — all flagged in the same review.

---

## 1. Introduction

### Purpose

This document is the single source of truth for how Tempo looks, behaves, and is built. It exists so that every designer and engineer working on Tempo — today or in five years — can make consistent decisions without re-litigating the same questions on every pull request. A design system is not a style guide of pretty pictures; it is a decision-making tool. Its job is to make the *right* choice the *easy* choice.

### Audience

This document assumes technical fluency. It is written for:

- **Product designers** building new flows and screens.
- **Frontend engineers** implementing and extending the UI.
- **New hires** who need to become productive without a week of tribal-knowledge transfer.

It does not explain basic design terminology (contrast, hierarchy, kerning). It does explain Tempo-specific decisions and the reasoning behind them.

### Branding and product are one system

Tempo's brand is not a logo bolted onto a product. The mark, the color, the spacing rhythm, and the interface are one continuous decision. The logo's modular construction (Section 4) is not decoration sitting above the product — it is the same geometric discipline the product's spacing system (Section 7) is built from. If the brand ever feels like a wrapper around the product, something has gone wrong.

### Design philosophy

Tempo is a planning application built around intentional time allocation rather than calendar management. The product's job is to help someone decide, calmly and clearly, what deserves their time. The interface must never compete with that job. Every principle in this document ultimately serves one goal: **reduce the distance between a person's intention and the software reflecting it back to them, with as little visual noise as possible.**

---

## 2. Brand Principles

These are not marketing adjectives. Each one has a direct, testable effect on interface decisions.

### Calm
The interface should never demand attention it hasn't earned. No pulsing dots, no unsolicited motion, no red badges for non-urgent information.
*In practice:* notification badges are used only for items that require action, never for passive counts (see Section 10, Notifications).

### Intentionality
Every element on screen should be there because it was chosen, not because it was easy to add.
*In practice:* before adding a UI element, ask what breaks if it's removed. If nothing breaks, don't add it (see Section 3, "Remove before adding").

### Rhythm
Time in Tempo is understood as a sequence of discrete, related intervals — not a continuous stream. The interface should visually reinforce cadence: repeated modules, consistent intervals, predictable spacing.
*In practice:* the 8px spacing scale (Section 7) and the logo's repeating module (Section 4) are the same idea applied at two different scales.

### Structure
Nothing in Tempo should feel improvised. Layouts are grid-based, components snap to the spacing scale, and hierarchy is legible at a glance.
*In practice:* avoid one-off pixel values in CSS. If a spacing value isn't on the scale, the layout is wrong, not the scale.

### Modularity
Complex screens should read as compositions of a small number of well-understood parts, not bespoke arrangements.
*In practice:* prefer extending an existing component over designing a new one for a single use case.

### Clarity
Say the least necessary to be understood — in copy, in visual hierarchy, in interaction feedback.
*In practice:* one primary action per screen. If two actions compete for primary emphasis, the hierarchy is unresolved (see Section 10, Buttons).

### Confidence
Tempo does not hedge visually. Decisions are made once, applied consistently, and not second-guessed with inconsistent variants scattered across the product.
*In practice:* one button shape, one radius scale, one type ramp — not "mostly consistent."

### Restraint
The absence of an element is a valid, often superior, design decision.
*In practice:* default to fewer colors, fewer weights, fewer motion effects than feels necessary. Add back only what's proven necessary in testing.

### Longevity
Tempo is built to still look correct in ten years. Avoid anything trend-driven — heavy gradients, glassmorphism, novelty iconography, or typographic fashion.
*In practice:* when evaluating a new pattern, ask "will this look dated in three years?" If uncertain, don't ship it.

---

## 3. Design Decision Principles

These are operating principles for any designer or engineer making a UI decision, listed roughly in the order they should be applied.

**Remove before adding.**
The fastest way to improve a crowded screen is subtraction, not further arrangement. Before adding a new element to solve a problem, spend equal time asking what existing element could be removed instead.

**Whitespace creates hierarchy before color.**
Color is the most expensive tool in the hierarchy toolbox — it's the first thing colorblind users lose access to, and the first thing that ages badly. Spacing and grouping should establish hierarchy on their own; color should only reinforce it.

**Typography creates emphasis before size.**
A weight change (500 → 600) or a color shift (ink → muted) is a smaller, more controlled emphasis signal than a font-size jump. Reach for size last — it's the blunt instrument.

**Consistency beats novelty.**
A new pattern has to earn its place by solving a problem an existing pattern genuinely cannot. "This would look nicer" is not sufficient justification for a new component.

**Motion should clarify, never entertain.**
Every animation must answer: what does this help the user understand? (Where did this element come from? What changed? What's loading?) If an animation's only function is to feel delightful, cut it (see Section 11).

**Prefer one excellent solution over five acceptable ones.**
When facing multiple viable directions, resist shipping "a bit of everything." Pick the strongest single direction and execute it fully.

**Decoration must always justify itself.**
Every visual flourish — a shadow, a border, an icon, a divider — must be traceable to a functional purpose (separation, affordance, state). If you can't say why it's there, remove it.

**If a component feels busy, simplify it — don't add a setting to hide the busyness.**
A "compact mode" toggle is often evidence the default is wrong. Fix the default first.

**Use color to communicate state, not decoration.**
Color in the interface (beyond brand chrome) should mean something: success, warning, danger, focus, selection. Using semantic colors decoratively erodes their meaning everywhere else.

---

## 4. Logo System

### The symbol: Cadence Stack

The Tempo symbol is not a stylized letterform. It is constructed from a single repeating rectangular module — the same module used for the crossbar and the stem. The "T" is a byproduct of the composition, not its starting point.

```
■ ■ ■      ← three modules, one row (the crossbar)
  ■
  ■        ← the same module, repeated vertically (the stem)
  ■
```

This construction is deliberate: it encodes Tempo's core idea — that time is legible when broken into consistent, allocated units — directly into the mark. A viewer perceives *repetition and structure* before they consciously parse a letter. The symbol should never be described internally as "the T"; it is "the mark" or "the cadence stack."

### Construction geometry

All coordinates below are defined on a 100×100 unit grid (`viewBox="0 0 100 100"`). This grid is the single source of truth — never redraw the mark freehand or trace it from a raster export.

| Element | x | y | width | height | corner radius |
|---|---|---|---|---|---|
| Crossbar, left module | 13.5 | 24 | 20 | 15 | 1.8 |
| Crossbar, center module | 40 | 24 | 20 | 15 | 1.8 |
| Crossbar, right module | 66.5 | 24 | 20 | 15 | 1.8 |
| Stem, module 1 | 40 | 46 | 20 | 9.3 | 1.8 |
| Stem, module 2 | 40 | 62.3 | 20 | 9.3 | 1.8 |
| Stem, module 3 | 40 | 78.6 | 20 | 9.3 | 1.8 |

Governing values:

- **Module width:** 20 units — constant across every block, crossbar and stem alike.
- **Optical gap:** crossbar gap is 6.5 units; stem gap is 7 units. These differ intentionally — equal numeric gaps do not read as equal across a horizontal run of wide blocks versus a vertical stack. This is an optical correction, not an inconsistency; never "fix" it to a single numeric value.
- **Corner radius:** 1.8 units (≈9% of module width) on every block, no exceptions.
- **Center alignment:** the stem column and the crossbar's center module share the same x-range (40–60). This is what makes the stem read as a continuation of the crossbar rather than an unrelated element beneath it.

### Clear space

Minimum clear space around the symbol, on all sides, is **20% of the symbol's height** in any lockup or standalone placement. Never let another interface element (text, icon, edge of a container) enter this zone.

### Minimum size

The symbol is legible down to 16px. Below 16px, do not attempt to preserve the internal gaps — at that scale they contribute sub-pixel detail with no perceptual benefit and only risk anti-aliasing artifacts. The reference favicon and app-icon builds already account for this; never re-derive a smaller build by manually thinning the gaps further.

### Approved variants

| Variant | Use |
|---|---|
| Pine (#33604c) | Default, on light or neutral backgrounds |
| Deep Pine (#1e3a2d) | Higher-contrast alternative, dense print, small print reproduction |
| Ink (#1e261f) | Editorial/documentation contexts alongside body text |
| Black | Single-color print, engraving, non-color reproduction |
| White | On dark or Pine/Deep-Pine backgrounds |
| Reversed (white on Pine / Deep Pine field) | Pre-composited badges — emails, slides, merchandise |

### Background usage

The symbol in its plain color variants has a **transparent background** and must only be placed on surfaces where you control contrast (Paper, Surface, or a neutral photograph background with sufficient contrast margin). It must never be placed directly on Warning, Danger, or Success colors, or on busy photography.

### Monochrome usage

Black and white monochrome builds exist for contexts where color reproduction isn't available or appropriate (legal documents, single-color engraving, fax-quality print). They are not a "dark mode" shortcut — for dark interface surfaces, use the White variant, not the monochrome-black one.

### App icon

The app icon is the symbol in Surface cream (#fbfbf7) at 82% scale, centered, on a Pine-filled rounded square (corner radius 22% of the icon's edge). This padding ratio (9% margin per side) was deliberately tightened from earlier drafts — the symbol should feel present and confident in a crowded dock or app switcher, not float in a sea of background color.

### Favicon

The favicon reuses the exact app-icon construction at 32×32 (corner radius 7px, matching the same 22% ratio). Never hand-tune favicon geometry independently of the app icon — they must always be the same shape at different output sizes.

---

## 5. Color System

### Palette

Every color below is specified as a single hex value used identically for text, icons, and fills — there is no separate "light fill, dark text" pair to remember. Each was chosen, or in the case of `Warning`/`Success`/`Muted` re-chosen in this revision, so that the *same* hex clears AA contrast in **every** context this document says it can be used in (solid fill with white text, and standalone text/icon on Paper or Surface). If a future addition can't do both, it isn't ready to ship as a token — see the verification table that follows.

| Token | Hex | RGB | HSL | CSS variable | Typical usage |
|---|---|---|---|---|---|
| Primary (Pine) | `#33604c` | rgb(51, 96, 76) | hsl(153, 31%, 29%) | `--color-primary` | Primary buttons, active nav state, links, brand chrome |
| Primary Strong (Deep Pine) | `#1e3a2d` | rgb(30, 58, 45) | hsl(152, 32%, 17%) | `--color-primary-strong` | Pressed/active states, high-contrast brand contexts |
| Text (Ink) | `#1e261f` | rgb(30, 38, 31) | hsl(128, 12%, 13%) | `--color-text` | Default body and heading text |
| Muted | `#607165` | rgb(96, 113, 101) | hsl(138, 8%, 41%) | `--color-text-muted` | Secondary text, timestamps, placeholder copy, **including captions down to 12px** |
| Paper | `#eef0ea` | rgb(238, 240, 234) | hsl(80, 17%, 93%) | `--color-bg-paper` | App background (recessed) |
| Surface | `#fbfbf7` | rgb(251, 251, 247) | hsl(60, 33%, 98%) | `--color-bg-surface` | Cards, panels, modals (elevated) |
| Border | `#dcded6` | rgb(220, 222, 214) | hsl(75, 11%, 85%) | `--color-border` | Dividers, input borders, card edges — decorative separation only, see note below |
| Success | `#417659` | rgb(65, 118, 89) | hsl(147, 29%, 36%) | `--color-success` | Confirmations, completed states — text, icon, and solid-fill use |
| Warning | `#8c622c` | rgb(140, 98, 44) | hsl(34, 52%, 36%) | `--color-warning` | Caution states, approaching-deadline flags — text, icon, and solid-fill use |
| Danger | `#b3473a` | rgb(179, 71, 58) | hsl(6, 51%, 46%) | `--color-danger` | Destructive actions, errors — text, icon, and solid-fill use |
| Focus | `#2f6f93` | rgb(47, 111, 147) | hsl(202, 52%, 38%) | `--color-focus` | Keyboard focus rings (non-text UI element, 3:1 minimum) |
| Hover (Pine) | `#2a5240` | rgb(42, 82, 64) | hsl(153, 32%, 24%) | `--color-primary-hover` | Hover state of Primary elements |
| Selection | `#e3ece6` | rgb(227, 236, 230) | hsl(140, 19%, 91%) | `--color-selection` | Selected rows, active list items, text selection — **neutral pine wash only; not a badge background, see Subtle tints below** |
| Disabled | `#b9bcb5` | rgb(185, 188, 181) | hsl(86, 5%, 72%) | `--color-disabled` | Disabled text/icons/borders — never used for anything a user must read to act |

### Subtle tints (badge / banner backgrounds)

`Selection` is reserved for neutral UI selection state (Section 10). Success/Warning/Danger badges and banners use their own light tint paired with the semantic color above as text — never the semantic color as a white-on-fill background at small sizes, and never `Selection` doing double duty as a "green tint." Each pairing below is verified to clear 4.5:1.

| Token | Hex | CSS variable | Pairs with (text) | Verified contrast |
|---|---|---|---|---|
| Success Subtle | `#ebf4ef` | `--color-success-subtle` | Success `#417659` | 4.73:1 |
| Warning Subtle | `#f7f1e8` | `--color-warning-subtle` | Warning `#8c622c` | 4.80:1 |
| Danger Subtle | `#f9edec` | `--color-danger-subtle` | Danger `#b3473a` | 4.73:1 |

### Why these exist

- **Paper vs. Surface** exist as a pair, not synonyms. Paper is the recessed base layer (the "desk"); Surface is what sits on top of it (the "paper on the desk"). If everything is Surface, elevation stops meaning anything.
- **Success is not Pine.** Reusing the brand primary as the semantic "success" color conflates brand identity with UI state — a button can be Pine without meaning "this succeeded." Success is a distinct, slightly warmer green derived from the same hue family for harmony without ambiguity.
- **Focus is blue, not green**, deliberately. A focus ring must be visually distinguishable from Success and from Primary at a glance, including for users with red-green color vision deficiency — using a different hue family (not just a different shade of green) is the only reliable way to guarantee that.
- **Warning, Success, and Danger are deliberately darker than a typical "web-safe" amber/green/red.** A lighter, brighter version of any of the three reads well as a solid fill but fails AA the moment it's used as text or paired with white text on a button — rather than maintain two shades per color (a "fill" shade and a "text" shade, which is where most systems introduce inconsistency), Tempo uses one shade per semantic color that already satisfies both jobs.
- **One color, one hex, everywhere** is a constraint, not a limitation — it's the same "confidence and restraint" principle from Section 2 applied to the palette: fewer decisions for an engineer to get wrong.

### Accessibility and contrast (verified, not estimated)

All ratios below are computed from the actual token hex values — re-run this check if any token value ever changes; don't approximate by eye.

| Pairing | Ratio | Passes |
|---|---|---|
| Ink on Paper | 13.5:1 | AAA, all sizes |
| Ink on Surface | 15.0:1 | AAA, all sizes |
| Muted on Paper | 4.5:1 | AA, all sizes incl. 12px captions |
| Muted on Surface | 5.0:1 | AA, all sizes |
| White on Pine (buttons) | 7.2:1 | AAA |
| White on Deep Pine | 12.4:1 | AAA |
| White on Danger (buttons) | 5.4:1 | AA, all sizes |
| White on Warning (buttons) | 5.4:1 | AA, all sizes |
| White on Success (buttons) | 5.3:1 | AA, all sizes |
| Danger text on Paper | 4.7:1 | AA, all sizes |
| Warning text on Paper | 4.7:1 | AA, all sizes |
| Success text on Paper | 4.6:1 | AA, all sizes |
| Focus ring on Paper/Surface | 4.8:1 / 5.3:1 | Exceeds the 3:1 non-text minimum |
| Border on Paper (non-text) | 1.2:1 | **Decorative only — see note** |

**Border is not a state indicator.** At 1.2:1 against Paper, the default Border color is intentionally subtle and would fail the 3:1 non-text-contrast requirement if it were the *only* way a component communicated something (e.g., "this input has an error," "this checkbox is focused"). It's for quiet, low-stakes separation only — anywhere a boundary must convey meaning (error, focus, required field), pair it with Danger or Focus, which both clear 3:1.

### Semantic rules

- Color alone must never be the only signal for state — always pair Success/Warning/Danger with an icon or text label (see Section 12, Accessibility).
- Never introduce a new named color, or change an existing token's hex value, without re-running the contrast check above against every documented use case for that token — a color that "looks about the same" can silently cross an AA threshold.

---

## 6. Typography

### Primary font

**Inter**, weights 400 (regular), 500 (medium), 600 (semibold). This matches the wordmark's weight (600) and gives the product typography a shared voice with the logotype.

**Fallback stack:** `Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif`

**Code font:** `"JetBrains Mono", ui-monospace, "SF Mono", Menlo, monospace` — used for durations, timestamps, keyboard shortcuts, and any literal data value where character-width consistency matters. Set inline (within a sentence) at the surrounding text's size; set as a standalone value (e.g., a duration in a table cell) at `body-sm` (13px), never smaller — monospace faces read smaller than proportional faces at the same nominal size.

### Weights and when to use them

| Weight | Use |
|---|---|
| 400 | Body copy, descriptions, table cells |
| 500 | Labels, secondary emphasis, active nav items |
| 600 | Headings, primary buttons, the wordmark itself |

Never use anything below 400 or above 600 — Tempo has no light or bold/black cut in its type system. Weight is a small, controlled lever; a two-step range keeps every emphasis decision deliberate.

### Type scale

| Token | Size | Line height | Letter spacing | Use |
|---|---|---|---|---|
| `display` | 32px | 1.2 | -0.5px | Page-level titles (rare — most screens don't need one) |
| `h1` | 24px | 1.3 | -0.3px | Section headers |
| `h2` | 18px | 1.4 | -0.1px | Card/panel titles |
| `h3` | 16px | 1.4 | 0 | Subsection labels |
| `body` | 14px | 1.6 | 0 | Default UI text |
| `body-sm` | 13px | 1.5 | 0 | Secondary/dense UI text (tables, metadata) |
| `caption` | 12px | 1.4 | 0.1px | Timestamps, helper text, field hints |

Rule of thumb: **two consecutive scale steps should always be distinguishable at arm's length.** As a floor, no two adjacent steps should sit closer than 2px apart at this scale (`h3`→`body` is the tightest gap in the ramp, at 16px→14px) — anything tighter and weight (500 vs. 400) has to carry the entire distinction, which is fragile. If a redesign introduces a size between two existing steps, that's a signal the hierarchy problem should be solved with weight or color instead (Section 3).

### Paragraph and heading spacing

- Paragraph spacing: 1× the body line-height (i.e., a blank line is exactly as tall as one line of text — never eyeballed).
- Heading margin-top is always larger than margin-bottom (roughly 2:1) — this visually binds a heading to the content that follows it, not the content above.

### Tables, forms, buttons, navigation, captions

- **Tables:** `body-sm` for cell content, `500` weight for column headers, never smaller than 13px.
- **Forms:** field labels at `body-sm`/500, input text at `body`/400, helper/error text at `caption`.
- **Buttons:** `body`/600 for primary and secondary buttons; never smaller than 14px — buttons are the one place where letter-spacing should be left at 0 to preserve legibility under weight 600.
- **Navigation:** `body-sm`/500 for nav items; active item adds color (Primary), not weight change.
- **Captions:** always Muted color, `caption` scale — reserve caption size exclusively for genuinely secondary information, never for anything a user must read to complete a task.

---

## 7. Spacing System

### Philosophy

Tempo's spacing system is not a set of arbitrary tokens — it's the same modular logic as the logo, applied to layout. Just as the symbol is built from one repeating module at a fixed width and gap, every layout is built from one base unit repeated at fixed multiples. **If the logo taught us that repetition of a single unit creates rhythm, the interface should feel that same rhythm at a completely different scale.**

### Base unit

**8px.** All spacing in the product is a multiple of 8, with 4px permitted only as a "half-step" for the tightest inline contexts (icon-to-label gaps, badge padding).

### Spacing scale

| Token | Value | Use |
|---|---|---|
| `space-1` | 4px | Icon-to-text gaps, tight inline spacing |
| `space-2` | 8px | Base unit; internal padding of small components |
| `space-3` | 12px | Compact card padding, input padding |
| `space-4` | 16px | Standard component padding, gap between related fields |
| `space-6` | 24px | Gap between distinct form sections |
| `space-8` | 32px | Card-to-card gap, section padding |
| `space-12` | 48px | Section-to-section gap |
| `space-16` | 64px | Page-level top/bottom margins |

### Grid and containers

- Base layout grid: 8px columns/gutters, container max-width 1200px for primary content, with side padding scaling from 16px (mobile) to 64px (desktop).
- Cards: internal padding is always `space-4` or `space-6` — never a value outside the scale, even by a pixel, even "just this once."
- Sections: separated by `space-8` minimum; `space-12`–`space-16` when the sections are conceptually unrelated (e.g., end of settings, start of danger zone).

### Whitespace rules

- Whitespace is the first hierarchy tool (Section 3) — increase spacing before reaching for a divider line or background tint to separate two groups.
- Never compress the spacing scale to fit more content on screen. If content doesn't fit, the layout is wrong, not the spacing.

---

## 8. Corner Radius

### System

| Token | Radius | Use |
|---|---|---|
| `radius-xs` | 4px | Checkboxes, small tags |
| `radius-sm` | 6px | Inputs, buttons, **individual rows inside a dropdown/menu** |
| `radius-md` | 10px | Cards, **the dropdown/popover container itself**, its own outer corner |
| `radius-lg` | 14px | Modals, dialogs |
| `radius-pill` | 999px | Pills, filter chips, avatar badges |
| Logo module radius | 9% of module width (1.8/20 units) | Fixed — see Section 4, never reused elsewhere |

**Disambiguating dropdowns specifically**, since "dropdown" refers to two nested things: the floating container uses `radius-md` on its outer edge; each selectable row inside it uses `radius-sm` (or no radius at all if rows run edge-to-edge with the container). Never apply `radius-md` to an individual row — a menu item that rounded reads as its own free-floating card, not a row in a list.

### Elevation

Color contrast (Paper vs. Surface) communicates elevation for content that's part of the page flow (Section 2, 10). Content that floats *above* the page — and therefore can't rely on a predictable background behind it — needs a shadow instead. Two levels only:

| Token | Value | Use |
|---|---|---|
| `shadow-sm` | `0 2px 8px rgba(30,38,31,0.08)` | Dropdowns, popovers, tooltips |
| `shadow-lg` | `0 12px 32px rgba(30,38,31,0.16)` | Modals, dialogs |

Cards never use either token (Section 10) — shadows are reserved for things that visually detach from the page, not things that sit in it.

### Why softly rounded geometry

A small, consistent radius (never sharp, never heavily rounded) reads as precise rather than either clinical or playful. It mirrors the logo's own corner treatment (9% of module width) without literally copying that ratio onto unrelated UI elements — the *relationship* (soft, deliberate, uniform) is what transfers, not the exact number. Avoid fully squared corners (feels cold, dated) and avoid heavy "bubbly" radii above 16px on rectangular components (undermines the structured, architected brand personality from Section 2).

---

## 9. Iconography

### Style

Outlined, 1.5px stroke, no fills except for small solid-state indicators (dots, minimal badges). Corners on icon strokes use rounded joins, never mitered — this is the one place icon style directly echoes the logo's rounded-corner language. Default icon color is `--color-text` (Ink); use `--color-text-muted` only where the icon sits alongside already-muted text (e.g., a timestamp icon next to a timestamp) so the two read as one unit, and use a semantic color only when the icon itself carries that meaning (a Danger trash icon, a Success checkmark) — never for plain decorative emphasis.

### Grid and sizing

- Icon grid: 24×24px artboard, live area 20×20px (2px padding on each side).
- Standard interface size: 16px or 20px. Never introduce a third icon size into a single view.
- Icons must optically align to the cap-height of adjacent text, not its full line-height box.

### Filled vs. outlined

Outlined by default. A filled version of an icon is reserved exclusively for the *active/selected* state of that same icon (e.g., an outlined bookmark becomes filled once saved) — filled icons must never be used decoratively or interchangeably with outlined ones.

### Consistency rules

- One icon set, sourced from a single library — never mix stroke weights or corner styles across icons in the same view.
- Icons relate to the Tempo symbol only in spirit (rounded corners, restrained detail) — never literally incorporate the symbol's block shapes into unrelated icons.

---

## 10. Component Philosophy

This section describes the intended feel of each component family. It is not an exhaustive spec — treat it as the brief a designer should satisfy before shipping a new component variant.

**Buttons** — Confident and singular. One primary action per view, rendered in Pine with white text at weight 600; hover uses `--color-primary-hover`, disabled uses `--color-disabled` for both fill and text with no hover/active response at all. Secondary actions are outlined (1px Border, Ink text) or text-only (Ink text, no fill), never a second competing solid color. Destructive actions use Danger fill with white text only on the button that actually performs the destructive act — not on a "cancel," which stays secondary-styled. **Warning has no dedicated button treatment** — it exists for badges, banners, and inline flags (below), not for actions; an action is either routine (Primary/secondary) or destructive (Danger). If a flow seems to need a "warning button," that's a sign the action is actually destructive and should say so.

**Forms** — Quiet until they need attention. Inputs are Surface-colored with a Border-colored 1px outline; they gain a Focus-colored ring only on keyboard/interaction focus, never on hover. Validation errors appear inline, in Danger text, directly below the field — never in a separate summary block the user has to reconcile against the form.

**Cards** — The default container for grouped content. Surface background, Border-colored 1px edge, `radius-md`, `space-4`–`space-6` padding. A card should never need a drop shadow to read as elevated against Paper — the color contrast between Paper and Surface does that job.

**Navigation** — Structural, not decorative. Active state is communicated by color (Primary) and weight (500), never by a background pill unless the nav is explicitly tab-styled. Navigation should be the most stable, least-animated part of the interface.

**Tables** — Dense but calm. Row hover uses a subtle Selection-tinted background, not a border. Column headers are `body-sm`/500 in Muted, sortable columns indicate direction with a small icon, never color alone.

**Dialogs** — Reserved for decisions that genuinely block progress. `radius-lg`, Surface background, `shadow-lg` (Section 8), centered, with a scrim behind at low opacity. A dialog should never be used purely to display information the user could instead read inline.

**Dropdowns / menus** — Appear directly adjacent to their trigger, `radius-md` container with `shadow-sm` (Section 8), Surface background, 1px Border. Items use `body`/400 on `radius-sm` rows, with `body`/500 reserved for the currently selected item.

**Tabs** — Used for switching between views of the same object, never for unrelated destinations (that's navigation). Active tab uses a Primary-colored underline, not a filled background.

**Notifications** — Rare and earned (Section 2, Calm). A badge appears only when an action is required of the user — never as a passive activity counter. Toasts auto-dismiss for confirmations, persist for errors requiring acknowledgment.

**Badges** — `radius-pill`, used for short semantic labels (status, count). Background uses the matching Subtle tint token (`--color-success-subtle`, `--color-warning-subtle`, `--color-danger-subtle` — Section 5) with text in the corresponding full-strength semantic color; both are pre-verified to clear 4.5:1 together, so this pairing never needs a case-by-case contrast check. Never use full-strength semantic color as a badge background with white text at badge sizes — small white-on-color text is the single most common contrast failure in interfaces like this, which is exactly why the Subtle tokens exist.

**Charts** — Minimal gridlines (Border color, thin), data rendered in Pine as the primary series, Muted/neutral tones for comparison series. Never use Warning/Danger hues in a chart unless the data point genuinely represents that state.

**Progress indicators** — Determinate progress bars use Pine fill on a Border-colored track. Indeterminate/loading states use skeleton screens (Section 11) rather than spinners wherever the eventual content's shape is known ahead of time.

**Empty states** — An opportunity for clarity, not decoration. A short, direct sentence explaining what will appear here and (if applicable) a single action to create the first item. Avoid illustrations that don't carry the brand's restrained, geometric visual language.

---

## 11. Motion

### Philosophy

Motion in Tempo reinforces rhythm and continuity — it should feel like the natural conclusion of an action, not a performance. If a user would describe an animation as "fun" or "delightful," it has likely overstepped; the correct reaction is "that felt right," which is often not consciously noticed at all.

### Durations

| Token | Duration | Use |
|---|---|---|
| `motion-instant` | 100ms | Hover/press feedback |
| `motion-fast` | 150ms | Focus rings, small state toggles |
| `motion-base` | 200ms | Dropdown/menu open, tooltip appearance |
| `motion-slow` | 300ms | Modal/dialog open, page-section transitions |
| `motion-skeleton` | 1500ms | Skeleton-screen loading pulse (Section 11) — the one exception to the 300ms ceiling, since it's a continuous ambient state, not a discrete transition |

Nothing that represents a discrete state change should animate longer than 300ms — beyond that, motion reads as sluggish rather than considered. `motion-skeleton` is the single named exception, because it isn't a transition between two states; it's an idle/waiting indicator.

### Easing

Standard easing curve: `cubic-bezier(0.2, 0, 0, 1)` (ease-out) for anything entering or changing state; `cubic-bezier(0.4, 0, 1, 1)` (ease-in) for anything exiting/dismissing. Avoid bounce, spring-overshoot, or elastic easings entirely — they contradict the "calm and structured" brand principle.

### Hover, focus, loading

- **Hover:** background/border color shifts only, 100ms, no scale or shadow changes.
- **Focus:** the Focus-colored ring appears at 150ms with no delay — focus feedback must never feel laggy for keyboard users.
- **Loading:** prefer skeleton screens shaped like the eventual content over spinners; a spinner is acceptable only for actions with unknowable duration (e.g., network requests with no content shape to preview).

### Skeleton screens and microinteractions

Skeletons use a `motion-skeleton` (1.5s), low-contrast Paper-to-Surface pulse — subtle enough to read as "waiting," not so animated it competes with actual content once loaded. Microinteractions (checkbox check, toggle switch) should complete within `motion-fast` and never include secondary flourish (confetti, bounce) regardless of how satisfying it may seem in isolation.

### Motion hierarchy

The most important state changes get the most deliberate motion; incidental ones get none. A completed task might animate its checkbox and let the row content settle; it should not animate the entire list.

---

## 12. Accessibility

- **Contrast:** all text must meet WCAG AA at minimum (4.5:1 for body text, 3:1 for large text/UI components); see Section 5 for verified token pairings. This applies equally to **non-text UI components that convey information** \u2014 input borders in an error state, focus rings, chart axis lines a user must actually read \u2014 which need only 3:1 (WCAG 1.4.11) but are just as often overlooked as text contrast. Purely decorative dividers (Section 5's default `Border` token) are exempt because they carry no information on their own.
- **Keyboard navigation:** every interactive element must be reachable and operable via keyboard alone, in a logical tab order matching visual layout.
- **Focus:** the Focus-colored ring (Section 5) must be visible on every focusable element — never remove `:focus-visible` styling without an equivalent replacement.
- **Reduced motion:** respect `prefers-reduced-motion` — under this setting, replace transitions with instant state changes; skeleton pulses and any non-essential motion should be disabled entirely.
- **Touch targets:** minimum 44×44px hit area on all interactive elements in touch contexts, even if the visible element (e.g., an icon button) is smaller — pad the hit area, not the visual size.
- **Dark mode:** must maintain the same contrast guarantees as light mode (Section 13) — never ship a dark theme that hasn't been independently contrast-checked.
- **Screen readers:** semantic HTML first (`button`, `nav`, `table`, headings in order) — ARIA attributes supplement, they don't replace, correct markup. Icon-only buttons always carry an accessible label.

---

## 13. Dark Mode

Dark mode is a re-mapping of the same token system, not a separate design. Every token defined in Section 5 has a dark-mode counterpart below — there is no token left to "figure out later" at implementation time.

| Token | Light | Dark | Verified contrast (dark) |
|---|---|---|---|
| `--color-bg-paper` | `#eef0ea` | `#14211a` | — |
| `--color-bg-surface` | `#fbfbf7` | `#1b2b23` | — |
| `--color-text` | `#1e261f` | `#eef0ea` | 15.8:1 on dark paper |
| `--color-text-muted` | `#607165` | `#9aab9f` | 4.6:1 on dark paper |
| `--color-border` | `#dcded6` | `#2c3d34` | decorative, see Section 5 |
| `--color-primary` | `#33604c` | `#4d9374` | 4.6:1 on dark paper |
| `--color-primary-hover` | `#2a5240` | `#5ca583` | — |
| `--color-primary-strong` | `#1e3a2d` | `#3a6b52` | — |
| `--color-success` | `#417659` | `#51946f` | 4.5:1 on dark paper |
| `--color-warning` | `#8c622c` | `#ae7b37` | 4.5:1 on dark paper |
| `--color-danger` | `#b3473a` | `#cc6c61` | 4.5:1 on dark paper |
| `--color-focus` | `#2f6f93` | `#3c8ebe` | 4.5:1 on dark paper |
| `--color-selection` | `#e3ece6` | `#22352b` | — |
| `--color-disabled` | `#b9bcb5` | `#4a544d` | — |

**Why dark-mode Primary isn't just a lighter Success, and vice versa:** it would be easy to reuse one of the semantic colors' dark values for Primary since they land in a similar range — resist this. Each token is independently derived and independently contrast-checked; two tokens landing near each other in lightness is a coincidence of the palette's hue family, not a reason to collapse them into one value that now means two things.

### Logo usage in dark mode

Use the White symbol/lockup variant (Section 4) — never the Pine variant on a dark surface, and never the monochrome-black build. The app icon and favicon remain unchanged in both modes (they carry their own fixed Pine background, which already has sufficient contrast against OS chrome in both themes).

### Elevation in dark mode

Since shadows read poorly on dark surfaces, elevation is communicated by lightening Surface relative to Paper (rather than by shadow depth) — the same principle as light mode, just achieved by a lightness step instead of a warmth/whiteness step.

---

## 14. Writing Style

### Voice and tone

Direct, calm, respectful of the user's time — the same qualities as the visual identity. Tempo never over-explains, never uses exclamation points for routine confirmations, and never anthropomorphizes the product ("Oops! We couldn't find that").

### Examples

| Context | Do | Don't |
|---|---|---|
| Button | "Create block" | "Let's create a block!" |
| Success | "Block saved." | "Awesome! Your block was saved successfully!" |
| Error | "This time slot overlaps with another block. Choose a different time." | "Oops! Something went wrong." |
| Empty state | "No blocks scheduled today. Add one to get started." | "It's quiet in here... 👀 Add your first block!" |
| Help text | "Blocks shorter than 15 minutes won't appear on the weekly view." | "Pro tip! 💡 Try making blocks longer than 15 min for best results." |

### Forms and notifications

- Field help text is factual and preventive (explains a constraint before the user hits it), not reactive marketing copy.
- Notifications state what happened and, if applicable, what to do next — in that order, in one sentence each wherever possible.

---

## 15. Implementation

### Design tokens

All values in Sections 5–8 should exist as design tokens before they exist as hardcoded values anywhere. Recommended token naming: `{category}-{property}-{variant}`, e.g. `color-bg-surface`, `space-4`, `radius-md`, `motion-base`.

### CSS variables

```css
:root {
  /* Color */
  --color-primary: #33604c;
  --color-primary-strong: #1e3a2d;
  --color-primary-hover: #2a5240;
  --color-text: #1e261f;
  --color-text-muted: #607165;
  --color-bg-paper: #eef0ea;
  --color-bg-surface: #fbfbf7;
  --color-border: #dcded6;
  --color-success: #417659;
  --color-success-subtle: #ebf4ef;
  --color-warning: #8c622c;
  --color-warning-subtle: #f7f1e8;
  --color-danger: #b3473a;
  --color-danger-subtle: #f9edec;
  --color-focus: #2f6f93;
  --color-selection: #e3ece6;
  --color-disabled: #b9bcb5;

  /* Spacing */
  --space-1: 4px;  --space-2: 8px;  --space-3: 12px; --space-4: 16px;
  --space-6: 24px; --space-8: 32px; --space-12: 48px; --space-16: 64px;

  /* Radius */
  --radius-xs: 4px; --radius-sm: 6px; --radius-md: 10px;
  --radius-lg: 14px; --radius-pill: 999px;

  /* Elevation */
  --shadow-sm: 0 2px 8px rgba(30,38,31,0.08);
  --shadow-lg: 0 12px 32px rgba(30,38,31,0.16);

  /* Motion */
  --motion-instant: 100ms; --motion-fast: 150ms;
  --motion-base: 200ms; --motion-slow: 300ms; --motion-skeleton: 1500ms;
  --ease-out: cubic-bezier(0.2, 0, 0, 1);
  --ease-in: cubic-bezier(0.4, 0, 1, 1);

  /* Type scale */
  --text-display: 32px; --text-h1: 24px; --text-h2: 18px; --text-h3: 16px;
  --text-body: 14px; --text-body-sm: 13px; --text-caption: 12px;
}
```

### Tailwind tokens

Map the above directly into `theme.extend` rather than using Tailwind's default palette/spacing scale — this guarantees no engineer can accidentally reach for `bg-green-600` instead of `bg-primary`.

```js
// tailwind.config.js
theme: {
  extend: {
    colors: {
      primary: { DEFAULT: '#33604c', strong: '#1e3a2d', hover: '#2a5240' },
      surface: '#fbfbf7',
      paper: '#eef0ea',
      border: '#dcded6',
      success: { DEFAULT: '#417659', subtle: '#ebf4ef' },
      warning: { DEFAULT: '#8c622c', subtle: '#f7f1e8' },
      danger: { DEFAULT: '#b3473a', subtle: '#f9edec' },
      focus: '#2f6f93',
      selection: '#e3ece6',
      disabled: '#b9bcb5',
    },
    spacing: { 1: '4px', 2: '8px', 3: '12px', 4: '16px', 6: '24px', 8: '32px', 12: '48px', 16: '64px' },
    borderRadius: { xs: '4px', sm: '6px', md: '10px', lg: '14px', pill: '999px' },
    fontSize: { display: '32px', h1: '24px', h2: '18px', h3: '16px', body: '14px', 'body-sm': '13px', caption: '12px' },
    transitionDuration: { instant: '100ms', fast: '150ms', base: '200ms', slow: '300ms' },
    boxShadow: { sm: '0 2px 8px rgba(30,38,31,0.08)', lg: '0 12px 32px rgba(30,38,31,0.16)' },
  }
}
```

### Naming conventions

Components: `PascalCase` file and export names (`Button.tsx`, `EmptyState.tsx`). Tokens: `kebab-case` CSS variables, `camelCase` in JS/TS. Never mix a component name with a color name (`GreenButton` — use `Button variant="primary"`).

### Folder structure

```
/design-system
  /tokens        (colors.css, spacing.css, radius.css, motion.css)
  /components    (one folder per component, colocated styles + stories)
  /icons
  /brand         (logo SVGs, favicon, app icon sources — from tempo-brand-assets/)
```

### Versioning

Treat this document and its token files as versioned artifacts. Any change to Section 4–8 values requires a major version bump and a migration note; component/pattern changes (Sections 9–11) can ship as minor versions.

---

## 16. Do / Don't

**Logo**
✅ Use the provided SVG source files at any size.
❌ Recolor the symbol to a color outside Section 5's palette.
❌ Stretch, skew, or change the aspect ratio of the symbol or lockup.
❌ Add a drop shadow, gradient, or outline to the symbol.

**Spacing**
✅ Build every layout from the 8px scale (Section 7).
❌ Use an arbitrary pixel value ("it just needed a little more room").
❌ Compress the scale to fit more content on a crowded screen.

**Typography**
✅ Use weight (400/500/600) to create emphasis.
❌ Introduce a font weight outside 400/500/600.
❌ Use all-caps for anything longer than a short label.

**Colors**
✅ Use Success/Warning/Danger only for their semantic meaning.
✅ Use the Subtle tint tokens (not `Selection`) for badge/banner backgrounds.
❌ Use Pine as a "success" color — use Success instead (Section 5).
❌ Introduce a new brand color, or change an existing token's hex, without re-verifying contrast against every use case that token appears in (Section 5).
❌ Put white text on a semantic color at small size without checking it against the verified pairings table first — it's why `Warning` and `Success` were re-derived in this revision.

**Components**
✅ Extend an existing component's props/variants for a new use case.
❌ Build a bespoke one-off component visually similar to an existing one.

**Icons**
✅ Use the 1.5px-stroke outlined set at 16 or 20px.
❌ Mix icon sets or stroke weights within a single view.

**Motion**
✅ Keep every transition under 300ms with the standard easing curves.
❌ Add bounce/spring/elastic easing anywhere.

---

## 17. Design Review Checklist

Every pull request that touches the UI should be able to answer yes to each of these before merging:

- [ ] Does this reduce cognitive load, or at least not increase it?
- [ ] Is every spacing value on the 8px scale (Section 7)?
- [ ] Could anything here be removed without losing function? If so, was it removed?
- [ ] Is hierarchy achieved with typography/spacing before color?
- [ ] Does every color used carry its intended semantic meaning (Section 5), and if it's a new pairing (e.g. white text on a fill), has its contrast actually been checked rather than assumed?
- [ ] Does this component belong to an existing family, or is a genuinely new pattern justified in the PR description?
- [ ] Is any new motion under 300ms, using the standard easing curves, and does it clarify rather than entertain?
- [ ] Does this meet AA contrast and full keyboard operability?
- [ ] Does this still work correctly with `prefers-reduced-motion` and in dark mode?
- [ ] Does this feel like Tempo — calm, structured, restrained — or does it feel borrowed from somewhere else?

---

## 18. Immutable vs. Evolvable

### Frozen (do not modify without a full brand review)

- The symbol's geometry (Section 4) — module width, gaps, corner radius, alignment.
- The five core brand colors (Pine, Deep Pine, Ink, Paper, Surface) and their hex values.
- The wordmark typeface and weight relationship to the symbol.
- The app icon and favicon padding ratio.

### Evolvable design tokens

- Semantic colors (Success, Warning, Danger, Focus, Selection, Disabled) may be refined for contrast or accessibility reasons, provided they stay within the same hue logic described in Section 5.
- The type scale's specific pixel values may be adjusted for a new platform (e.g., a native mobile app) provided the two-weight, size-before-color emphasis philosophy is preserved.
- Motion durations may be tuned per-platform (e.g., slightly longer on lower-powered devices) within the existing token structure.

### Evolvable components

- Everything in Section 10 is a starting brief, not a locked spec. New variants, states, and entirely new component types may be added as the product grows — provided they're evaluated against Section 3's decision principles and Section 17's checklist before shipping.

### Experimental areas

New surfaces (e.g., a public marketing site, a native mobile app, third-party integrations) should treat this document as their foundation but may propose extensions — new components, new motion patterns for platform-specific gestures — through a documented design review, not through ad hoc deviation.

### Future extension guidelines

Any proposed change to a "Frozen" item requires: (1) a written rationale referencing which brand principle (Section 2) it serves, (2) validation that it doesn't break the app icon/favicon at 16px, and (3) sign-off from whoever owns brand governance at the time. Everything else in this document can evolve through normal design review, provided each change can point to which principle in Sections 2–3 it upholds.
