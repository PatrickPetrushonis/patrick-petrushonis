// src/utils/layout.js
// Measures footer's rendered height and writes it into styleTagId's
// textContent as a padding-bottom rule for contentSelector, so
// content isn't hidden underneath an absolutely-positioned footer.
// Re-measures on resize since that height can vary with responsive
// text wrapping.
//
// contentSelector's own style attribute is never touched directly -
// the computed value becomes a real stylesheet rule generated at
// runtime instead, via styleTagId's own textContent.
export function initFooterPadding(contentSelector, footerSelector, styleTagId) {
  const footer = document.querySelector(footerSelector);
  const styleTag = document.getElementById(styleTagId);
  if (!footer || !styleTag) return;

  function updatePadding() {
    styleTag.textContent = `${contentSelector} { padding-bottom: ${footer.offsetHeight}px; }`;
  }

  updatePadding();
  window.addEventListener('resize', updatePadding);
}
