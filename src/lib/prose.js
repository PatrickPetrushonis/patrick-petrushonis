import { getCollection } from 'astro:content';

// Only chapters whose publishDate has actually passed - a static
// build has no server to re-check this later, so a chapter dated in
// the future stays invisible until the site is rebuilt again after
// that date, not the moment it arrives.
export async function getPublishedChaptersSorted() {
  const chapters = await getCollection('prose', ({ data }) => data.publishDate <= new Date());
  return chapters.sort((a, b) => {
    if (a.data.volume !== b.data.volume) return a.data.volume - b.data.volume;
    return a.data.chapterNumber - b.data.chapterNumber;
  });
}

// Derived from the actual body text, never authored in frontmatter,
// so these can't drift from the real content as a chapter is edited.
export function estimateReadingStats(body) {
  const wordCount = body.trim().split(/\s+/).filter(Boolean).length;
  const readTimeMinutes = Math.max(1, Math.round(wordCount / 200));
  return { wordCount, readTimeMinutes };
}