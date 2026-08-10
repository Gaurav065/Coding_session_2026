/* ════════════════════════════════════════════════════════════
   SONAL'S STORY — interaction engine
   ════════════════════════════════════════════════════════════ */

// ── Backend-style config: change the password here ──────────
const CONFIG = {
  username: "Sonal",
  password: "stardust",          // ← set Sonal's secret key here (case-insensitive)
};

const $  = (s, c = document) => c.querySelector(s);
const $$ = (s, c = document) => [...c.querySelectorAll(s)];

/* ══════════════ 1 · STARFIELD (global backdrop) ══════════════ */
const starCanvas = $("#starfield");
const sctx = starCanvas.getContext("2d");
let stars = [];

function buildStars() {
  starCanvas.width = innerWidth;
  starCanvas.height = innerHeight;
  const n = Math.floor((innerWidth * innerHeight) / 6500);
  stars = Array.from({ length: n }, () => ({
    x: Math.random() * innerWidth,
    y: Math.random() * innerHeight,
    r: Math.random() * 1.4 + 0.3,
    tw: Math.random() * Math.PI * 2,
    ts: 0.5 + Math.random() * 1.5,
    depth: 0.15 + Math.random() * 0.85,
  }));
}
buildStars();
addEventListener("resize", buildStars);

// stars belong to the twilight prologue and the finale night sky —
// they fade away over the pastel celebration sections
let revealTop = Infinity, finaleTop = Infinity;
function cacheOffsets() {
  const r = $("#p-reveal"), f = $("#p-finale");
  if (r) revealTop = r.offsetTop;
  if (f) finaleTop = f.offsetTop;
}
addEventListener("load", cacheOffsets);
addEventListener("resize", cacheOffsets);

function starAlpha() {
  const vh = innerHeight;
  const fadeOut = Math.max(0, Math.min(1, (revealTop - scrollY) / (vh * 0.7)));
  const fadeIn  = Math.max(0, Math.min(1, (scrollY - (finaleTop - vh * 0.85)) / (vh * 0.6)));
  return Math.max(fadeOut, fadeIn);
}

/* ══════════════ 2 · MOUSE STATE + PARALLAX ══════════════ */
const mouse = { x: 0, y: 0, sx: 0, sy: 0 }; // raw + smoothed (-1..1)
function pointTo(cx, cy) {
  mouse.x = (cx / innerWidth) * 2 - 1;
  mouse.y = (cy / innerHeight) * 2 - 1;
  spawnSparkles(cx, cy);
}
addEventListener("mousemove", (e) => pointTo(e.clientX, e.clientY));
// touch devices: finger drags drive the parallax and sparkle trail
addEventListener("touchmove", (e) => {
  const t = e.touches[0];
  if (t) pointTo(t.clientX, t.clientY);
}, { passive: true });
addEventListener("touchstart", (e) => {
  const t = e.touches[0];
  if (t) pointTo(t.clientX, t.clientY);
}, { passive: true });

const parallaxEls = () => $$("[data-depth]");
let pEls = [];
function refreshParallax() { pEls = parallaxEls(); }
refreshParallax();

/* ══════════════ 3 · CURSOR SPARKLES ══════════════ */
const spkCanvas = $("#sparkles");
const kctx = spkCanvas.getContext("2d");
let sparkles = [];
let finaleActive = false;

function sizeAux() {
  spkCanvas.width = innerWidth; spkCanvas.height = innerHeight;
  cfCanvas.width = innerWidth;  cfCanvas.height = innerHeight;
}

function spawnSparkles(x, y) {
  const count = finaleActive ? 3 : (Math.random() < 0.35 ? 1 : 0);
  for (let i = 0; i < count; i++) {
    sparkles.push({
      x: x + (Math.random() - 0.5) * 14,
      y: y + (Math.random() - 0.5) * 14,
      vx: (Math.random() - 0.5) * 0.7,
      vy: -0.4 - Math.random() * 0.9,
      life: 1,
      decay: 0.012 + Math.random() * 0.02,
      r: 0.8 + Math.random() * (finaleActive ? 2.4 : 1.6),
      hue: 42 + Math.random() * 18,
    });
  }
  if (sparkles.length > 260) sparkles.splice(0, sparkles.length - 260);
}

/* ══════════════ 4 · CONFETTI ══════════════ */
const cfCanvas = $("#confetti");
const cctx = cfCanvas.getContext("2d");
let confetti = [];
const CF_COLORS = ["#ff8fb3", "#7fb2ff", "#ffd166", "#b8f0d4", "#d3b8ff", "#ffb08a", "#fff"];

function burstConfetti(n = 220) {
  for (let i = 0; i < n; i++) {
    confetti.push({
      x: innerWidth / 2 + (Math.random() - 0.5) * innerWidth * 0.5,
      y: innerHeight * 0.32 + (Math.random() - 0.5) * 120,
      vx: (Math.random() - 0.5) * 11,
      vy: -4 - Math.random() * 9,
      w: 5 + Math.random() * 7,
      h: 8 + Math.random() * 8,
      rot: Math.random() * Math.PI * 2,
      vr: (Math.random() - 0.5) * 0.25,
      color: CF_COLORS[(Math.random() * CF_COLORS.length) | 0],
      life: 1,
      decay: 0.0035 + Math.random() * 0.003,
      wobble: Math.random() * Math.PI * 2,
    });
  }
}

sizeAux();
addEventListener("resize", sizeAux);

/* ══════════════ 5 · MASTER RENDER LOOP ══════════════ */
let t = 0;
function frame() {
  t += 0.016;

  // smoothed mouse
  mouse.sx += (mouse.x - mouse.sx) * 0.06;
  mouse.sy += (mouse.y - mouse.sy) * 0.06;

  // stars
  sctx.clearRect(0, 0, starCanvas.width, starCanvas.height);
  const sA = starAlpha();
  const scrollShift = scrollY * 0.06;
  for (const s of sA < 0.02 ? [] : stars) {
    const a = (0.35 + 0.65 * Math.abs(Math.sin(s.tw + t * s.ts))) * sA;
    const px = s.x + mouse.sx * 22 * s.depth;
    let py = (s.y - scrollShift * s.depth) % starCanvas.height;
    if (py < 0) py += starCanvas.height;
    sctx.globalAlpha = a * 0.9;
    sctx.fillStyle = s.depth > 0.7 ? "#fff6dd" : "#dce6ff";
    sctx.beginPath();
    sctx.arc(px, py + mouse.sy * 14 * s.depth, s.r, 0, 7);
    sctx.fill();
  }
  sctx.globalAlpha = 1;

  // parallax elements
  for (const el of pEls) {
    const d = +el.dataset.depth;
    el.style.transform = `translate3d(${mouse.sx * d}px, ${mouse.sy * d * 0.7}px, 0)`;
  }

  // sparkles
  kctx.clearRect(0, 0, spkCanvas.width, spkCanvas.height);
  sparkles = sparkles.filter((p) => (p.life -= p.decay) > 0);
  for (const p of sparkles) {
    p.x += p.vx; p.y += p.vy;
    kctx.globalAlpha = p.life;
    kctx.fillStyle = `hsl(${p.hue} 95% 78%)`;
    kctx.shadowColor = `hsl(${p.hue} 95% 70%)`;
    kctx.shadowBlur = 8;
    kctx.beginPath();
    kctx.arc(p.x, p.y, p.r * p.life, 0, 7);
    kctx.fill();
  }
  kctx.shadowBlur = 0; kctx.globalAlpha = 1;

  // confetti
  cctx.clearRect(0, 0, cfCanvas.width, cfCanvas.height);
  confetti = confetti.filter((c) => c.life > 0 && c.y < innerHeight + 40);
  for (const c of confetti) {
    c.life -= c.decay;
    c.vy += 0.16;               // gravity
    c.vx *= 0.99; c.vy *= 0.992;
    c.wobble += 0.08;
    c.x += c.vx + Math.sin(c.wobble) * 0.8;
    c.y += c.vy;
    c.rot += c.vr;
    cctx.save();
    cctx.globalAlpha = Math.min(1, c.life * 2);
    cctx.translate(c.x, c.y);
    cctx.rotate(c.rot);
    cctx.scale(1, Math.sin(c.wobble));   // flutter
    cctx.fillStyle = c.color;
    cctx.fillRect(-c.w / 2, -c.h / 2, c.w, c.h);
    cctx.restore();
  }

  requestAnimationFrame(frame);
}
requestAnimationFrame(frame);

/* ══════════════ 6 · THE GATE ══════════════ */
const gate = $("#gate");
const gateForm = $("#gate-form");
const gateErr = $("#gate-error");
const journey = $("#journey");

$("#hint-btn").addEventListener("click", () => $("#hint-reveal").classList.add("show"));

gateForm.addEventListener("submit", (e) => {
  e.preventDefault();
  const pw = $("#password").value.trim().toLowerCase();
  if (pw === CONFIG.password.toLowerCase()) {
    unlock();
  } else {
    gateErr.classList.add("show");
    const card = $(".gate-card");
    card.classList.remove("shake");
    void card.offsetWidth;           // restart animation
    card.classList.add("shake");
  }
});

function unlock() {
  gateErr.classList.remove("show");
  gate.classList.add("unlocking");   // shackle swings open
  setTimeout(() => {
    gate.classList.add("open");
    document.body.classList.remove("locked");
    journey.setAttribute("aria-hidden", "false");
    scrollTo({ top: 0, behavior: "instant" });
    // kick off Panel I typewriter shortly after the gate dissolves
    setTimeout(() => observeAll(), 600);
  }, 900);
}

/* ══════════════ 7 · TYPEWRITER ══════════════ */
function typewrite(el, done) {
  const text = el.dataset.type;
  el.textContent = "";
  const caret = document.createElement("span");
  caret.className = "caret";
  el.appendChild(caret);
  let i = 0;
  (function step() {
    if (i < text.length) {
      const ch = text[i++];
      caret.before(document.createTextNode(ch));
      const pause = /[,…—.]/.test(ch) ? 220 : 34 + Math.random() * 40;
      setTimeout(step, pause);
    } else {
      setTimeout(() => { caret.remove(); done && done(); }, 900);
    }
  })();
}

/* ══════════════ 8 · SCROLL-TRIGGERED SEQUENCING ══════════════ */
const typedPanels = new WeakSet();

function observeAll() {
  // typewriter panels — one element at a time
  const typeObserver = new IntersectionObserver((entries) => {
    for (const en of entries) {
      if (!en.isIntersecting) continue;
      const panel = en.target;
      if (typedPanels.has(panel)) continue;
      typedPanels.add(panel);
      const txt = $(".type-text", panel);
      if (txt) typewrite(txt, () => panel.classList.add("typed"));
      else panel.classList.add("typed");
    }
  }, { threshold: 0.55 });
  $$(".panel-tome, .panel-heavens, .panel-chart, .panel-bright, .panel-woods")
    .forEach((p) => typeObserver.observe(p));

  // the big reveal — flash + confetti + pop-in
  let revealed = false;
  new IntersectionObserver((entries) => {
    for (const en of entries) {
      if (en.isIntersecting && !revealed) {
        revealed = true;
        $("#flash").classList.add("burst");
        setTimeout(() => burstConfetti(240), 260);
        setTimeout(() => burstConfetti(120), 1100);
        en.target.classList.add("shown");
        setTimeout(() => en.target.classList.add("typed"), 2100); // prompt after title lands
      }
    }
  }, { threshold: 0.45 }).observe($("#p-reveal"));

  // validation cards — spring-lock one by one
  const cardObserver = new IntersectionObserver((entries) => {
    for (const en of entries) {
      if (en.isIntersecting) {
        en.target.classList.add("locked");
        cardObserver.unobserve(en.target);
      }
    }
  }, { threshold: 0.45 });
  $$(".vcard").forEach((c) => cardObserver.observe(c));

  // cards panel prompt
  new IntersectionObserver((entries) => {
    entries.forEach((en) => en.isIntersecting && en.target.classList.add("shown"));
  }, { threshold: 0.3 }).observe($("#p-cards"));

  // finale — text fade + intensified cursor particles
  new IntersectionObserver((entries) => {
    for (const en of entries) {
      finaleActive = en.isIntersecting;
      if (en.isIntersecting) en.target.classList.add("shown");
    }
  }, { threshold: 0.4 }).observe($("#p-finale"));

  refreshParallax();
}

/* ══════════════ 9 · BACK TO TOP ══════════════ */
$("#back-to-top").addEventListener("click", () => {
  scrollTo({ top: 0, behavior: "smooth" });
});

/* keep focus on the password field at load */
addEventListener("load", () => $("#password").focus());
