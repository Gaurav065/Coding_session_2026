# ✦ Sonal's Story — an interactive birthday tale

A cinematic, narrative-driven birthday website that unlocks one scene at a time:
a locked stardust gateway → a typewritten fable across five atmospheric panels →
a pastel 3D celebration reveal → scroll-triggered encouragement cards → a glowing
paper-lantern finale with cursor-following light particles.

## Run it

No build step — it's plain HTML/CSS/JS. Either:

- double-click `index.html`, or
- serve it locally (needed only if your browser blocks Google Fonts on `file://`):

  ```
  python -m http.server 8123
  ```

  then open <http://localhost:8123>.

## The password

The gate's credentials live at the top of [`app.js`](app.js):

```js
const CONFIG = {
  username: "Sonal",
  password: "stardust",   // ← change Sonal's secret key here (case-insensitive)
};
```

The in-page "need a hint?" text is in `index.html` (`#hint-reveal`) — update it
if you change the password.

## The journey

| Scene | What happens |
| --- | --- |
| The Locked Gateway | Glassmorphism login card, ancient-lock icon; the shackle swings open on the right password |
| The Gilded Tome | "In far, far away lands… at around 10 PM." — typewriter over an open book |
| The Heavens Paused | New panel: moon + comets watching the arrival |
| The Star Chart | Orbits and an hourglass glyph — "a rare light was kindled…" |
| The World Grew Brighter | New panel: a rising trail of golden lights |
| The Whispering Woods | Forest clearing, fireflies, whispered kindness |
| The Big Reveal | Flash of light, confetti burst, 3D pastel "Happy Birthday, Sonal!" |
| The Validation Cards | Three spring-physics glass cards: The Journey, The Effort, The Light |
| The Grand Finale | Floating paper lantern, cursor sparkles, Back to Top |

Everything reacts gently to the mouse (parallax via `data-depth` attributes),
and the starfield fades out over the pastel celebration and returns for the
night-sky finale.
