# Thrillhikers — Scroll Animation Landing Page

A 4-page cinematic scrollytelling landing page for a hiking/adventure brand, built with plain HTML/CSS and GSAP + ScrollTrigger. No build step, no framework, no npm install required.

**Pages:**
1. **Cloud-parting intro** — fog splits left/right to reveal a misty mountain
2. **EXPLORE hero** — brand, nav, and headline stagger in over a golden-hour peak
3. **Cave reveal** — jagged black rock silhouettes slide in from all four edges to frame the view, then the camera pushes deeper (zoom + parallax) into a blue dusk peak
4. **Content** — headline text reveal followed by a staggered 3D-flip reveal of 4 destination cards

---

## Requirements

- Any modern web browser (Chrome, Edge, Firefox, Safari)
- An internet connection when viewing the page — GSAP, ScrollTrigger, and the Google Fonts (Inter, Bebas Neue) load from a CDN rather than being bundled locally
- Python 3 **or** Node.js installed, only if you want to run a local static server (recommended — see below). Not required if you just want to double-click `index.html`.

Nothing else needs to be downloaded or installed. There is no `package.json` and no build/compile step — every file here is served as-is.

## Getting the code

**Option A — clone the repo**
```bash
git clone https://github.com/Gaurav065/Coding_session_2026.git
cd Coding_session_2026/thrillhikers-landing
```

**Option B — download the ZIP**
1. Download `thrillhikers-landing.zip`
2. Extract it anywhere on your machine
3. Open a terminal in the extracted `thrillhikers-landing` folder

## Running it

### Quickest: open the file directly
Double-click `index.html` (or drag it into a browser window). The page works from a plain `file://` URL since nothing here calls an API or reads local files.

### Recommended: run a local static server
Serving over `http://` avoids occasional browser quirks with `file://` pages (e.g. some image/font caching behavior) and is closer to how it'll behave once actually deployed.

Using Python (already installed on most systems):
```bash
cd thrillhikers-landing
python -m http.server 8000
```
Then open **http://localhost:8000** in your browser.

Using Node.js instead, if you have it:
```bash
cd thrillhikers-landing
npx serve .
```
(follow the local URL it prints, usually http://localhost:3000)

### Stopping the server
Press `Ctrl+C` in the terminal where the server is running.

## Project structure

```
thrillhikers-landing/
├── index.html          # markup for all 4 pages
├── styles.css           # layout, layering, typography
├── script.js             # GSAP/ScrollTrigger animation logic
├── assets/
│   ├── page1-fog.jpg          # misty pine forest (page 1 background)
│   ├── page2-explore.jpg      # golden-hour peak (page 2 background)
│   ├── page3-dusk.jpg         # blue-hour peak (page 3 / cave background)
│   ├── card-everest.jpg       # destination card photo
│   ├── card-annapurna.jpg     # destination card photo
│   ├── card-monastery.jpg     # destination card photo
│   └── card-sunrise.jpg       # destination card photo
└── README.md            # this file
```

## Customizing

- **Swap a background photo**: replace the matching file in `assets/` (keep the same filename), or update the `background-image: url(...)` path in `index.html` for that page's `.bg` element.
- **Edit headline/copy**: text lives directly in `index.html` — search for `.explore-text`, `.headline`, or `.subcopy`.
- **Change animation timing**: all scroll-linked timelines are in `script.js`, grouped by page with comments (`PAGE 1`, `PAGE 2`, etc.). Each `.to()`/`.fromTo()` call's last argument is its start time inside that page's timeline.
- **Add/remove destination cards**: duplicate a `.card` block inside `#page-4` in `index.html`; the reveal animation in `script.js` (`.card` stagger) applies automatically to however many cards exist.

## Browser support

Built and tested against current Chrome/Edge. Uses standard CSS (flexbox, grid, `clip-path`, `mix-blend-mode`) and GSAP 3, both broadly supported in modern evergreen browsers. No IE11 support.

## Credits

Photography sourced from [Unsplash](https://unsplash.com) (free to use under the [Unsplash License](https://unsplash.com/license)). Fonts via [Google Fonts](https://fonts.google.com) (Inter, Bebas Neue). Animation powered by [GSAP](https://gsap.com) and its ScrollTrigger plugin.
