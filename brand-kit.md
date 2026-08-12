# TCS Brand Kit (extracted from tortclaimstrategies.com, Aug 7 2026)

Source: the marketing site is a Webflow build. Logo + palette pulled from the live homepage HTML/CSS.

## Logo
- **File (white-on-transparent, dark-theme-ready):** the navbar logo is an animated GIF
  (`Black-Transparent-Gif.gif`, 298 frames, 500×281). Despite the "Black" in the filename, the actual
  logo content is **white text + cyan/teal icon on transparent** — it is INVISIBLE on white and
  DESIGNED for dark backgrounds. Use it directly on the dark dashboard theme; do NOT put it on white.
- **Composition:** combination mark — a **shield** (cyan/teal gradient) containing an **ascending bar
  chart with an up-right arrow** (growth), beside the wordmark **"TORT CLAIM STRATEGIES"** in bold
  uppercase sans-serif (white with a faint cyan tint toward the bottom).
- **Extraction pitfall:** it's an animated GIF; naive first-frame extraction yields a solid-black
  frame. To get a usable still, pick the frame with the most non-transparent/non-black pixels
  (content-scored), then crop to bbox. A cleaned still is staged at `templates/../assets` if saved,
  else re-derive from the source URL:
  `https://cdn.prod.website-files.com/694923259de19a947a85fd1b/69651b515e4eea99e0303334_Black-Transparent-Gif.gif`

## Palette (hex, from site CSS)
- **Primary accent (cyan/teal):** `#32e6e2` (also `#6CFFF3`, `#71F9F9` variants) — use for status
  accents, links, the "priorities" highlight, owner tags.
- **Base/background:** near-black (`#0b0e13` / `#10141c` work well with the brand).
- **Text on dark:** white / off-white (`#e8eef5`), muted `#8a99ad`.
- **Status colors (dashboard convention, not from site):** red `#e5484d`, amber `#f5a524`, green `#30a46c`.

## Usage rule
Dark theme is the brand's native mode. Light/white content panels (tables, cards) sit ON the dark
background — this is the locked dashboard aesthetic ("dark with light tables", Andrew Aug 7 2026).
