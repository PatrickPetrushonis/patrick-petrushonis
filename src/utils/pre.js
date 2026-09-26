// src/utils/pre.js
// Dedents every <pre> block's content based on its first line's
// leading whitespace.
export function formatPreElements() {
  const preElements = document.querySelectorAll('pre');

  preElements.forEach((pre) => {
    const lines = pre.innerHTML.split('\n');
    const offset = lines[0]?.match(/^\s*/)?.[0]?.length || 0;

    const formattedLines = lines.map((line) => line.slice(offset));
    pre.innerHTML = formattedLines.join('\n');
  });
}
