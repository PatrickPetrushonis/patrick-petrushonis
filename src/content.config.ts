import { defineCollection } from 'astro:content';
import { z } from 'astro/zod';
import { file } from 'astro/loaders';

// Lives at src/content.config.ts (src/ root, no subfolder): the
// current Astro 5+ location for this file.
//
// order is a number, so it sorts correctly with normal numeric
// comparison.
const projects = defineCollection({
  loader: file('src/content/projects/projects.json'),
  schema: z.object({
    title: z.string(),
    order: z.number(),
    details: z.string(), // raw HTML, rendered via set:html - see Home.astro
  }),
});

export const collections = { projects };
