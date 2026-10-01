// src/utils/header.js
import { smoothScrollTo, initScrollThresholdClass } from './scroll.js';

export function initHeader() {
  // Scroll position can't be known at build time, so this needs
  // runtime JS, unlike the checkbox-driven icon animation defined in
  // CSS.
  const header = document.getElementById('site-header');
  if (header) initScrollThresholdClass(header, 100, 'header-container--slim');

  const navToggle = document.getElementById('nav-toggle');
  const navList = document.getElementById('nav-list');

  // .show-nav is the real class _header.scss's ul.show-nav rule
  // reacts to - the checkbox's own :checked state only drives the
  // icon animation via CSS; showing/hiding the list itself needs this
  // explicit toggle.
  navToggle?.addEventListener('change', () => {
    if (navToggle instanceof HTMLInputElement) {
      navList?.classList.toggle('show-nav', navToggle.checked);
    }
  });

  // Setting .checked programmatically doesn't fire a change event on
  // its own, so closing the nav after a link click needs both the
  // checkbox state and the class updated together, not just one.
  function closeNav() {
    if (navToggle instanceof HTMLInputElement) navToggle.checked = false;
    navList?.classList.remove('show-nav');
  }

  // Smooth scroll for same-page anchor links (About/Projects nav
  // items). Direct navigation to /#section-about from another page
  // still navigates normally here; Layout.astro's
  // initHashNavigationOnLoad handles the offset-aware scroll once
  // that page loads.
  document.querySelectorAll('[data-scroll="true"]').forEach((link) => {
    link.addEventListener('click', (e) => {
      const href = link.getAttribute('href') ?? '';
      const hashIndex = href.indexOf('#');
      if (hashIndex === -1) return;
      const onCurrentPage = href.startsWith('#') || href.slice(0, hashIndex) === window.location.pathname;
      if (!onCurrentPage) return; // let the browser navigate normally
      e.preventDefault();
      smoothScrollTo(href.slice(hashIndex));
      closeNav();
    });
  });

  // Includes the header-height offset so the target lands below the
  // fixed header.
  const logoLink = document.getElementById('logo-home-link');
  logoLink?.addEventListener('click', (e) => {
    e.preventDefault();
    smoothScrollTo('#section-top', 77);
    closeNav();
  });
}