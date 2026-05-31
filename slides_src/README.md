# Conversion Coach — presentation

A [Slidev](https://sli.dev) deck for the Conversion Coach project (Insurance AI /
UNIQA). The theme is **ported from the product's own design system**
(`../design_idea/healthcover-warm.css`) — UNIQA-style deep blue, warm cream, and
amber — so the slides look like the HealthCover journey they describe. The coach
nudge, persona chips, tariff cards and brand mark are recreated natively, so the
deck stays vector-crisp in the PDF.

## Develop

```bash
npm install
npm run dev        # opens localhost:3030, live reload
```

## Export to PDF

```bash
npm run export        # → slides-export.pdf (uses Playwright's bundled Chromium)
```

> **On this machine**, Playwright's bundled `chrome-headless-shell` segfaults, so
> use Brave (Chromium-based) instead — it's already installed:
>
> ```bash
> npm run export:brave   # → slides-export.pdf via /usr/bin/brave
> ```
>
> Both produce the same `slides-export.pdf`. To submit, copy it to the repo root
> (`cp slides-export.pdf ../slides.pdf`).

## Structure

| Path | What |
|---|---|
| `slides.md` | the deck — content + per-slide layout |
| `style.css` | the "Warm" design system, ported for slides (auto-loaded) |
| `layouts/` | `cover`, `section`, `statement`, and an overridden `default` (footer furniture) |
| `components/` | `Brand`, `PersonaSwitch`, `Persona`, `Nudge` (the coach popup, recreated) |

Fonts (Hanken Grotesk · Source Serif 4 · IBM Plex Mono) are pulled via the
`fonts:` headmatter in `slides.md`, matching the website.
