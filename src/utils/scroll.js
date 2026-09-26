// src/utils/scroll.js
// Vanilla client-side scroll utilities. Each function either does one
// thing directly or attaches its own listener; call the
// listener-attaching ones once from a component's own <script> tag
// rather than expecting a returned value to apply yourself.

export function smoothScrollTo(targetId, offset = 77) {
  const element = document.querySelector(targetId);
  if (!element) return;
  const targetPosition = element.offsetTop - offset;
  window.scrollTo({ top: targetPosition, behavior: 'smooth' });
}

export function scrollToTop() {
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

// Toggles className on element based on scroll position past
// threshold. Shared by every component that needs a scroll-triggered
// class change.
export function initScrollThresholdClass(element, threshold, className) {
  function update() {
    element.classList.toggle(className, window.scrollY > threshold);
  }
  update();
  window.addEventListener('scroll', update, { passive: true });
}

// On load, if the URL has a hash, smooth-scrolls to it with the same
// header-height offset used for in-page nav clicks. Needed because
// the browser's own native hash-scroll-on-load is instant and doesn't
// know about the fixed header's height - without this, arriving at
// /#section-about from another page lands the target section
// partially hidden behind the header.
export function initHashNavigationOnLoad(offset = 77) {
  const hash = window.location.hash;
  if (!hash) return;
  setTimeout(() => smoothScrollTo(hash, offset), 100);
}
