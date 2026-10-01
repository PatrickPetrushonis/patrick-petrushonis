// src/utils/theme.js
const STORAGE_KEY = 'theme';

export function readStoredTheme() {
  try {
    const value = localStorage.getItem(STORAGE_KEY);
    return value === 'light' || value === 'dark' ? value : null;
  } catch {
    return null; // storage can be unavailable (private mode, blocked cookies)
  }
}

export function storeTheme(theme) {
  try {
    localStorage.setItem(STORAGE_KEY, theme);
  } catch {
    // the choice still applies for this page view
  }
}

export function currentTheme() {
  const attribute = document.documentElement.getAttribute('data-theme');
  if (attribute === 'light' || attribute === 'dark') return attribute;
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
}

export function applyTheme(theme) {
  document.documentElement.setAttribute('data-theme', theme);
}

// Full behavior for the theme toggle button: sets the initial theme,
// keeps the button's accessible name describing the action a click
// performs, stores the choice on click, and follows the operating
// system live when no choice has been stored.
export function initThemeToggle(buttonId) {
  const button = document.getElementById(buttonId);
  const prefersDark = window.matchMedia('(prefers-color-scheme: dark)');

  function setThemeAndLabel(theme) {
    applyTheme(theme);
    button?.setAttribute(
      'aria-label',
      theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode',
    );
  }

  setThemeAndLabel(currentTheme());

  button?.addEventListener('click', () => {
    const next = currentTheme() === 'dark' ? 'light' : 'dark';
    setThemeAndLabel(next);
    storeTheme(next);
  });

  // With no saved choice, follow the operating system live.
  prefersDark.addEventListener('change', (event) => {
    if (readStoredTheme() === null) setThemeAndLabel(event.matches ? 'dark' : 'light');
  });
}