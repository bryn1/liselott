# DESIGN.md — Liselotts bokhylla (binding design truth)

version 1.0.0 (2026-11-13, MC 12447). The token spec is PLAN §9 verbatim
(PLAN-c3 §9 — "unchanged from cycle 1"). This file is the design truth of the
app: a token change lands here as a NEW version with the old copy archived and
labelled `SUPERSEDED — DO NOT USE` (workspace-convention §Versioned-truth), and
`scripts/contrast_check.py` reads its values from this file, so the document
and the stylesheet cannot drift apart (`tests/test_design_tokens.py` enforces
both directions).

Owner direction (binding, verbatim): "All books should have it's actual cover
photo. full impeccable build with nice look and view, calm and pleasant
without to much details and effects."

## Token table (§9 verbatim)

| token | value | use |
|---|---|---|
| --paper | #FAF6F1 | page background (warm paper) |
| --card | #FFFFFF | cards, form fields |
| --ink | #2E2B27 | body/headline text |
| --muted | #5E5750 | meta text (ISBN, dates) |
| --line | #E4DCCF | hairline borders |
| --accent | #6B7F65 | calm sage: active states, covers' halo |
| --link | #4E6348 | links (AA on paper and card) |
| --star | #B07A2B | rating stars (≥3:1, always with aria-label) |
| --danger | #8C4A3F | error copy |
| type | Lora (serif) 400/700 self-hosted woff2, fallback Georgia,serif; ALL text incl. UI — one voice | |
| scale | 17px root; 0.8125/1/1.125/1.375/1.625/2.056 rem; line-height 1.6 body, 1.2 headings; measure 62ch | |
| space | 4/8/12/16/24/40/64 (tokens --s1..--s7); page gutter 16, max width 720px content / 1080px shelf grid | |
| radius/shadow | 6px; ONE shadow level 0 1px 2px rgb(20 16 12 / .06) | |
| motion | transitions 120ms ease-out on opacity/background-color/border-color ONLY; `@media (prefers-reduced-motion: reduce)` disables all | |
| FORBIDDEN | parallax, scroll effects, animation libraries (GSAP incl.), gradients-as-decoration, glassmorphism, carousels, hover-lift, icon fonts | |

## The token set — `app/static/css/app.css` `:root` declares EXACTLY this

(One declaration per line; `tests/test_design_tokens.py` compares these values
byte-identically against the stylesheet, in both directions.)

```css
:root {
  --paper: #FAF6F1;
  --card: #FFFFFF;
  --ink: #2E2B27;
  --muted: #5E5750;
  --line: #E4DCCF;
  --accent: #6B7F65;
  --link: #4E6348;
  --star: #B07A2B;
  --danger: #8C4A3F;
  --s1: 4px;
  --s2: 8px;
  --s3: 12px;
  --s4: 16px;
  --s5: 24px;
  --s6: 40px;
  --s7: 64px;
  --radius: 6px;
  --shadow: 0 1px 2px rgb(20 16 12 / .06);
  --measure: 62ch;
  --font: "Lora", Georgia, "Times New Roman", serif;
}
```

## FORBIDDEN (§9 verbatim)

parallax, scroll effects, animation libraries (GSAP incl.),
gradients-as-decoration, glassmorphism, carousels, hover-lift, icon fonts.

## The rest of §9 (verbatim contract rows)

- **Cover placeholder:** `omslag-saknas.svg` — paper-colored rect, thin line
  border, one muted word "omslag". Its alt/copy carries the fix-me hint
  ("Omslag saknas — fixa") linking `/redigera/<id>` only on the bok page,
  never on `/cover/` (PLAN-c3 §9).
- **Stars input:** five radios with `<span aria-hidden>` stars +
  `aria-label "Betyg N av 5"`.
- **A11y:** all pages `lang="sv"`, single `h1`, visible `:focus-visible` ring
  2px --link, 375px-tested layout (shelf collapses to 2 columns; forms
  full-width).
- **Copy:** all Swedish, plain, lowercase-leaning ("Din hylla", "Sök",
  "Lägg till bok", "Betygsätt", "Logga in", "Sätt ditt lösenord",
  "Rekommendationer åt dig", "Att läsa").
- **Real covers are the visual life of the page** — the app shows each book's
  actual cover (§1, owner direction above); the placeholder is the honest
  not-yet state, never decoration.
