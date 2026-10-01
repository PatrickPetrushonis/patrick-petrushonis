import { defineCollection } from 'astro:content';
import { z } from 'astro/zod';
import { file, glob } from 'astro/loaders';

// Lives at src/content.config.ts (src/ root, no subfolder): the
// current Astro 5+ location for this file.
//
// order is a number, so it sorts correctly with normal numeric
// comparison. category distinguishes game-development work from
// prose-writing volumes within the same collection - the two are
// rendered as separate tab groups in Home.astro, not merged into one.
const projects = defineCollection({
  loader: file('src/content/projects/projects.json'),
  schema: z.object({
    title: z.string(),
    order: z.number(),
    category: z.enum(['game-development', 'prose-writing']),
    details: z.string(), // raw HTML, rendered via set:html - see Home.astro
  }),
});

// One Markdown file per chapter under src/content/prose/volume-N/.
// wordCount/readTimeMinutes are deliberately not schema fields - both
// are derived from the actual body text at render time (see
// src/lib/prose.js), never hand-authored, so they can't drift from
// the real content.
const prose = defineCollection({
  loader: glob({ pattern: '**/*.md', base: './src/content/prose' }),
  schema: z.object({
    volume: z.number(),
    chapterNumber: z.number(),
    title: z.string(),
    publishDate: z.date(),
    description: z.string().optional(),
  }),
});

export const collections = { projects, prose };