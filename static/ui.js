// CampusConnect UI micro-interactions (no layout changes)
// - Ripple on .btn, .hero-btn, .nav a
// - Reveal-on-scroll for .card, .assignment-card, .surface, .table
// - Subtle tilt on hover for cards (uses CSS vars)

(function() {
  function onReady(fn) {
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', fn);
    } else {
      fn();
    }
  }

  onReady(() => {
    const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    // Ripple effect
    const rippleTargets = Array.from(document.querySelectorAll('.btn, .hero-btn, .nav a'));

    rippleTargets.forEach((el) => {
      // Ensure container can clip ripple
      const style = window.getComputedStyle(el);
      if (style.position === 'static') {
        el.style.position = 'relative';
      }
      el.style.overflow = (style.overflow === 'visible') ? 'hidden' : style.overflow;

      el.addEventListener('click', (e) => {
        try {
          const rect = el.getBoundingClientRect();
          const ripple = document.createElement('span');
          ripple.className = 'ripple';
          const size = Math.max(rect.width, rect.height);
          const x = (e.clientX || (rect.left + rect.width / 2)) - rect.left - size / 2;
          const y = (e.clientY || (rect.top + rect.height / 2)) - rect.top - size / 2;
          ripple.style.width = ripple.style.height = size + 'px';
          ripple.style.left = x + 'px';
          ripple.style.top = y + 'px';
          el.appendChild(ripple);
          ripple.addEventListener('animationend', () => ripple.remove());
        } catch (_) {
          // no-op
        }
      });
    });

    if (!reduceMotion) {
      // Reveal-on-scroll
      const revealTargets = Array.from(document.querySelectorAll('.card, .assignment-card, .surface, .table'));
      revealTargets.forEach((el) => el.classList.add('reveal-init'));

      const io = new IntersectionObserver((entries, obs) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            entry.target.classList.add('reveal-in');
            entry.target.classList.remove('reveal-init');
            obs.unobserve(entry.target);
          }
        });
      }, { threshold: 0.15, rootMargin: '0px 0px -10% 0px' });

      revealTargets.forEach((el) => io.observe(el));

      // Tilt on hover for cards
      const tiltTargets = Array.from(document.querySelectorAll('.card, .assignment-card'));

      tiltTargets.forEach((el) => {
        let rafId = null;
        function onMove(e) {
          const rect = el.getBoundingClientRect();
          const px = (e.clientX - rect.left) / rect.width;  // 0..1
          const py = (e.clientY - rect.top) / rect.height; // 0..1
          const rotY = (px - 0.5) * 6; // -3..3 deg
          const rotX = (0.5 - py) * 6; // -3..3 deg
          if (rafId) cancelAnimationFrame(rafId);
          rafId = requestAnimationFrame(() => {
            el.style.setProperty('--tiltX', rotY.toFixed(2) + 'deg');
            el.style.setProperty('--tiltY', rotX.toFixed(2) + 'deg');
          });
        }
        function onEnter() { el.classList.add('tilt-hover'); }
        function onLeave() {
          if (rafId) cancelAnimationFrame(rafId);
          el.classList.remove('tilt-hover');
          el.style.setProperty('--tiltX', '0deg');
          el.style.setProperty('--tiltY', '0deg');
        }
        el.addEventListener('pointerenter', onEnter, { passive: true });
        el.addEventListener('pointermove', onMove, { passive: true });
        el.addEventListener('pointerleave', onLeave, { passive: true });
      });
    }
  });
})();
