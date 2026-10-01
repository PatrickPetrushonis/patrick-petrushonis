import rss from '@astrojs/rss';
import { getPublishedChaptersSorted } from '../lib/prose.js';

export async function GET(context) {
  const chapters = (await getPublishedChaptersSorted()).sort(
    (a, b) => b.data.publishDate - a.data.publishDate,
  );

  return rss({
    title: 'Series title goes here',
    description: 'Series description goes here.',
    site: context.site,
    items: chapters.map((entry) => ({
      title: `Vol. ${entry.data.volume}, Ch. ${entry.data.chapterNumber}: ${entry.data.title}`,
      pubDate: entry.data.publishDate,
      description: entry.data.description,
      link: `/chapters/${entry.id}/`,
    })),
  });
}