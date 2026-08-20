gsap.registerPlugin(ScrollTrigger);

document.addEventListener('DOMContentLoaded', () => {

  /* ===================================================
     PAGE 1 — grand cloud-parting establishing shot
  =================================================== */
  gsap.timeline({ delay: 0.3 })
    .to('.fog-left', { xPercent: -145, duration: 2.6, ease: 'power2.inOut' })
    .to('.fog-right', { xPercent: 145, duration: 2.6, ease: 'power2.inOut' }, '<')
    .to('.fog-low', { yPercent: 100, duration: 2.2, ease: 'power2.inOut' }, '<0.3')
    .to('.page1-caption', { opacity: 1, duration: 1 }, '-=1.2');

  /* ===================================================
     PAGE 2 — hero UI reveal, replays on re-entry
  =================================================== */
  gsap.timeline({
    scrollTrigger: {
      trigger: '#page-2',
      start: 'top top',
      end: '+=90%',
      pin: true,
      anticipatePin: 1,
      toggleActions: 'play reverse play reverse'
    }
  })
    .to('.hero-ui .brand', { opacity: 1, y: 0, duration: 0.7, ease: 'power2.out' })
    .to('.hero-ui .nav-link', { opacity: 1, y: 0, duration: 0.6, stagger: 0.12, ease: 'power2.out' }, '<')
    .to('.explore-text span', { opacity: 1, y: 0, duration: 0.85, stagger: 0.06, ease: 'back.out(1.6)' }, '-=0.3');

  /* ===================================================
     PAGE 3 — parallax rock reveal + depth zoom
     (rocks SLIDE in from the four edges — no iris/mask
     scaling, so it never reads as a tunnel contraction)
  =================================================== */
  gsap.timeline({
    scrollTrigger: {
      trigger: '#page-3',
      start: 'top top',
      end: '+=220%',
      scrub: 1,
      pin: true,
      anticipatePin: 1
    }
  })
    // four rock masses slide in from their own edge, slightly staggered
    .fromTo('.rock-top', { yPercent: -100 }, { yPercent: 0, duration: 0.4, ease: 'power2.out' }, 0)
    .fromTo('.rock-left', { xPercent: -100 }, { xPercent: 0, duration: 0.4, ease: 'power2.out' }, 0.04)
    .fromTo('.rock-right', { xPercent: 100 }, { xPercent: 0, duration: 0.4, ease: 'power2.out' }, 0.04)
    .fromTo('.rock-bottom', { yPercent: 100 }, { yPercent: 0, duration: 0.4, ease: 'power2.out' }, 0.08)
    .to('.cave-nav .nav-link', { opacity: 1, y: 0, duration: 0.3, stagger: 0.06 }, 0.2)
    .to('.figure', { opacity: 1, duration: 0.25 }, 0.34)
    .to('.scroll-cue', { opacity: 1, duration: 0.25 }, 0.38)

    // hold the framed view briefly
    .to({}, { duration: 0.12 })

    // push deeper into the cave: walls loom larger (scale from their
    // own outer edge, never translate) while the mountain beyond zooms
    // and drifts upward, faint haze breathing back in
    .to('.figure', { opacity: 0, duration: 0.2 }, 0.62)
    .to('.scroll-cue', { opacity: 0, duration: 0.2 }, 0.62)
    .to('.rock-left', { scaleX: 1.18, duration: 0.75, ease: 'power1.inOut' }, 0.62)
    .to('.rock-right', { scaleX: 1.18, duration: 0.75, ease: 'power1.inOut' }, 0.62)
    .to('.rock-top', { scaleY: 1.15, duration: 0.75, ease: 'power1.inOut' }, 0.62)
    .to('.rock-bottom', { scaleY: 1.15, duration: 0.75, ease: 'power1.inOut' }, 0.62)
    .to('.clouds-faint', { opacity: 0.5, duration: 0.6 }, 0.68)
    .to('.cave-bg', { scale: 1.45, y: '-11%', duration: 1, ease: 'power1.inOut' }, 0.62);

  gsap.set('.rock-left', { transformOrigin: 'left center' });
  gsap.set('.rock-right', { transformOrigin: 'right center' });
  gsap.set('.rock-top', { transformOrigin: 'top center' });
  gsap.set('.rock-bottom', { transformOrigin: 'bottom center' });

  /* ===================================================
     PAGE 4 — headline + creative card reveal
  =================================================== */
  gsap.utils.toArray('.headline .line').forEach(line => {
    const words = line.textContent.split(' ');
    line.innerHTML = words.map(w => `<span class="word">${w}&nbsp;</span>`).join('');
    gsap.set(line.querySelectorAll('.word'), { display: 'inline-block', y: '110%', opacity: 0 });
  });

  gsap.to('.headline .word', {
    y: '0%',
    opacity: 1,
    duration: 0.9,
    stagger: 0.045,
    ease: 'power3.out',
    scrollTrigger: { trigger: '.headline', start: 'top 85%' }
  });

  gsap.set('.subcopy', { opacity: 0, y: 20 });
  gsap.to('.subcopy', {
    opacity: 1,
    y: 0,
    duration: 0.8,
    ease: 'power2.out',
    scrollTrigger: { trigger: '.subcopy', start: 'top 90%' }
  });

  const cards = gsap.utils.toArray('.card');
  cards.forEach((card, i) => {
    const fromLeft = i % 2 === 0;
    gsap.set(card, {
      opacity: 0,
      y: 70,
      rotateY: fromLeft ? -70 : 70,
      rotateZ: fromLeft ? -6 : 6,
      transformPerspective: 1000,
      transformOrigin: fromLeft ? 'left center' : 'right center'
    });
  });

  gsap.to('.card', {
    opacity: 1,
    y: 0,
    rotateY: 0,
    rotateZ: 0,
    duration: 1,
    stagger: 0.16,
    ease: 'power3.out',
    scrollTrigger: { trigger: '.cards', start: 'top 82%' }
  });

  /* ===================================================
     PAGE DOTS — active state + click-to-jump
  =================================================== */
  document.querySelectorAll('.page').forEach((page, i) => {
    ScrollTrigger.create({
      trigger: page,
      start: 'top center',
      end: 'bottom center',
      onEnter: () => setActiveDot(i + 1),
      onEnterBack: () => setActiveDot(i + 1)
    });
  });

  function setActiveDot(n) {
    document.querySelectorAll('.dot').forEach(d => {
      d.classList.toggle('active', d.dataset.page === String(n));
    });
  }

  // pinned-section measurements can be off until images + web fonts have
  // finished loading and reflowed the page — force a clean recalculation
  document.fonts.ready.then(() => ScrollTrigger.refresh());
  window.addEventListener('load', () => ScrollTrigger.refresh());

});
