# patrickpetrushonis.github.io

Personal portfolio and serial fiction site, built with Astro 7
(`^7.3.5`). Originally a Vite + React project; converted to Astro's
`astro-static` profile with the same portfolio content, SCSS, and
visual design, served via a custom domain over GitHub Pages.

## How weekly chapter releases actually work

Read this before writing a chapter ahead of its release date.

This is a static site: there is no server checking the current date on
each visitor's request. A chapter's `publishDate` is only evaluated
**at build time** - when `npm run build` runs, or when the deploy
workflow rebuilds the site on a push. A chapter dated for next Monday
does not appear on Monday on its own. It appears the next time the
site is actually rebuilt *after* that date has passed.

In practice, this means one of two things has to be true for the
weekly-release plan to work as intended:

- **A scheduled rebuild** (a `schedule:` trigger added to
  `.github/workflows/deploy.yml`) rebuilds and redeploys automatically
  on a recurring basis, so a chapter written and committed in advance
  goes live on its own once its date passes.
- **A manual push on release day** - write and commit each chapter
  exactly when it's meant to go live. No scheduling infrastructure
  needed, but `publishDate` only really matters then for sort order
  and the RSS feed, not for hiding pre-written content.

No scheduled rebuild currently exists in this repo. Until one is
added, chapters go live only when something (a push, a manual
`workflow_dispatch` run) actually triggers a rebuild after their
`publishDate`.

## Before this works

- `npm install @astrojs/rss` - not currently a dependency;
  `src/pages/rss.xml.js` imports it and the build will fail without
  it.
- Confirm `site` is set in `astro.config.mjs`. RSS feed item links are
  generated from it; without it, feed links won't resolve to full
  URLs.
- `rss.xml.js` currently has placeholder feed title/description text
  (`'Series title goes here'` / `'Series description goes here.'`) -
  replace both before this goes live. Unlike the chapter `.md`
  placeholders, these don't visually stand out as fake.

## Project Structure

```text
/
├── public/
│   └── app/img/                 # referenced from source as /app/img/... - never
│                                 # via a relative path into public/, since Vite
│                                 # doesn't resolve public/ assets that way
├── src/
│   ├── components/
│   │   ├── Footer.astro
│   │   ├── Header.astro
│   │   ├── Home.astro
│   │   └── ScrollToTop.astro
│   ├── content/
│   │   ├── projects/
│   │   │   └── projects.json    # the Projects section's actual content
│   │   └── prose/
│   │       ├── volume-1/
│   │       │   ├── chapter-01.md
│   │       │   └── chapter-02.md
│   │       └── volume-2/
│   │           └── chapter-01.md
│   ├── content.config.ts        # schema for both collections above
│   ├── lib/
│   │   └── prose.js             # shared sort/filter/reading-stat helpers
│   ├── layouts/
│   │   └── Layout.astro
│   ├── pages/
│   │   ├── 404.astro
│   │   ├── index.astro
│   │   ├── rss.xml.js
│   │   ├── chapters/
│   │   │   └── [...slug].astro  # one route, every chapter
│   │   └── volumes/
│   │       └── [volume].astro   # one route, every volume's table of contents
│   ├── styles/
│   │   ├── components/           # Header, Footer, Layout, Main partials
│   │   ├── pages/                 # About, Banner, Buttons, Projects, Sections
│   │   ├── utilities/             # variables, functions, mixins, helpers
│   │   └── main.scss              # entry point; @use's the above
│   └── utils/
│       ├── layout.js
│       ├── pre.js
│       └── scroll.js
├── .github/
│   └── workflows/
│       └── deploy.yml
└── package.json
```

No frontend framework is installed; every component is a plain
`.astro` file. Client-side interactivity (scroll-triggered classes,
smooth-scroll offsets, hash navigation, footer padding) lives in
`src/utils/*.js`, imported directly into each component's own
`<script>` tag rather than through a framework integration.

## Content

### Projects

The Projects section's data lives in `src/content/projects/projects.json`,
typed by the schema in `src/content.config.ts`. Adding, removing, or
reordering a project means editing that JSON file. `order` is a plain
number, not a string, so no parsing is needed to sort by it. Nothing
in any `.astro` file hardcodes project data directly.

### Chapters

A new chapter is a new Markdown file at
`src/content/prose/volume-N/chapter-NN.md` (the collection itself is
named `prose` in `content.config.ts`), with this frontmatter:

```yaml
---
volume: 1
chapterNumber: 3
title: "Chapter Title"
publishDate: 2026-01-15
description: "One or two sentences - used as both the page's meta description and the RSS item description."
---
```

- `publishDate` must be a bare date (`2026-01-15`), not a quoted
  string - the schema expects a real date value, not text.
- **Sort order comes entirely from `chapterNumber` in the frontmatter,
  not the filename.** Renaming `chapter-03.md` to something else
  changes nothing about where it appears; only `chapterNumber` does.
- Word count and estimated reading time are never authored by hand -
  both are computed from the actual chapter text in
  `src/lib/prose.js`, so they can't drift from the real content as
  a chapter is edited. The reading-time estimate uses a fixed 200
  words/minute constant, defined in that same file, with no particular
  citation behind it - a rough approximation, not a measured figure.
- Nothing currently checks for a duplicate or skipped `chapterNumber`
  within a volume. Getting this right is a manual responsibility for
  now.

## Commands

All commands run from the project root:

| Command | Action |
| :--- | :--- |
| `npm install` | Installs dependencies |
| `npm run dev` | Starts the local dev server at `localhost:4321` |
| `npm run type-check` | Runs `astro check` on its own |
| `npm run build` | Runs `type-check`, then builds to `./dist/`; a type error fails the build, not just the check |
| `npm run preview` | Previews the production build locally |
| `npm run lint` | Runs ESLint over the project |

## Deployment

Pushing to `master` triggers `.github/workflows/deploy.yml`, which
builds the site (`withastro/action`) and deploys it
(`actions/deploy-pages`) automatically. There is no manual deploy
step and no `gh-pages` package. The original Vite + React version of
this repo used `npm run deploy` (the `gh-pages` CLI, pushing to a
`gh-pages` branch); that workflow is fully retired.

No scheduled rebuild exists yet - see "How weekly chapter releases
actually work" above before relying on pre-written, future-dated
chapters going live on their own.

The site is served through a custom domain (CNAME), configured in this
repo's GitHub Pages settings; the domain, not the raw
`*.github.io` URL, is what visitors and any existing links should
resolve to.

## Known gaps

- **The nav has one link per volume with published content
  (currently Volume 1 and Volume 2), added by hand.** A new volume
  needs a manual `<li>` added to `Header.astro` when it starts;
  nothing generates this list from the actual collection.
- **No series landing page exists** connecting the volumes to each
  other - currently `/volumes/1/`, `/volumes/2/`, etc. are only
  reachable directly or from each other's chapter pages, not from one
  shared entry point.
- **`package.json`'s `"name"` field is still `"master-config-template"`**
  - the generic scaffold's default, never renamed to reflect this
  project.

## Learn more

[Astro documentation](https://docs.astro.build)