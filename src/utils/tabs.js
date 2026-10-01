// src/utils/tabs.js
// Finds every .project-tabs container on the page and wires up its own
// radio/thumbnail/details syncing independently. One call handles every
// group - Astro dedupes an identical script across multiple instances of
// the same component, so this runs once regardless of how many groups
// are rendered, and discovers each one's own ids from its own radios
// rather than needing them passed in from the server.
export function initAllRadioTabGroups() {
  document.querySelectorAll('.project-tabs').forEach((container) => {
    const radios = container.querySelectorAll('.project-tab__radio');
    const ids = [...radios].map((radio) => radio.id.replace(/^tab-/, ''));
    initRadioTabGroup(container, ids);
  });
}

function initRadioTabGroup(container, ids) {
  function update() {
    for (const id of ids) {
      const radio = document.getElementById(`tab-${id}`);
      const link = container.querySelector(`[data-tab="tab-${id}"]`);
      const details = container.querySelector(`[data-for-tab="tab-${id}"]`);
      if (!(radio instanceof HTMLInputElement) || !link || !details) continue;
      link.classList.toggle('selected', radio.checked);
      details.classList.toggle('selected', radio.checked);
    }
  }

  // A plain <button> doesn't drive a radio's checked state the way a
  // label[for] association would, so the click handler sets it
  // directly and calls update() itself: assigning .checked in script
  // doesn't fire a change event. Scoped to this container, so a click
  // in one group's markup never touches another group's elements.
  container.querySelectorAll('.project__link').forEach((link) => {
    link.addEventListener('click', () => {
      const targetId = link.getAttribute('data-tab');
      const radio = document.getElementById(targetId);
      if (!(radio instanceof HTMLInputElement)) return;
      radio.checked = true;
      update();
    });
  });

  update();
}