# patrickpetrushonis.github.io

Personal portfolio site, built with Astro. Originally a Vite + React
project; converted to Astro's `astro-static` profile with the same
content, SCSS, and visual design, served via a custom domain over
GitHub Pages.

## Project Structure

```text
/
├── public/
│   └── app/img/               # referenced from source as /app/img/... - never
│                               # via a relative path into public/, since Vite
│                               # doesn't resolve public/ assets that way
├── src/
│   ├── components/
│   │   ├── Footer.astro
│   │   ├── Header.astro
│   │   ├── Home.astro
│   │   └── ScrollToTop.astro
│   ├── content/
│   │   └── projects/
│   │       └── projects.json  # the Projects section's actual content
│   ├── content.config.ts      # schema for the collection above
│   ├── layouts/
│   │   └── Layout.astro
│   ├── pages/
│   │   ├── 404.astro
│   │   └── index.astro
│   ├── styles/
│   │   ├── components/        # Header, Footer, Layout, Main partials
│   │   ├── pages/              # About, Banner, Buttons, Projects, Sections
│   │   ├── utilities/          # variables, functions, mixins, helpers
│   │   └── main.scss           # entry point; @use's the above
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

The Projects section's data lives in `src/content/projects/projects.json`,
typed by the schema in `src/content.config.ts`. Adding, removing, or
reordering a project means editing that JSON file. `order` is a plain
number, not a string, so no parsing is needed to sort by it. Nothing
in any `.astro` file hardcodes project data directly.

## Commands

All commands run from the project root:

| Command | Action |
| :--- | :--- |
| `npm install` | Installs dependencies |
| `npm run dev` | Starts the local dev server at `localhost:4321` |
| `npm run type-check` | Runs `astro check` on its own |
| `npm run build` | Runs `type-check`, then builds to `./dist/`; a type error fails the build, not just the check |
| `npm run preview` | Previews the production build locally |

## Deployment

Pushing to `master` triggers `.github/workflows/deploy.yml`, which
builds the site (`withastro/action`) and deploys it
(`actions/deploy-pages`) automatically. There is no manual deploy
step and no `gh-pages` package. The original Vite + React version of
this repo used `npm run deploy` (the `gh-pages` CLI, pushing to a
`gh-pages` branch); that workflow is fully retired.

The site is served through a custom domain (CNAME), configured in this
repo's GitHub Pages settings; the domain, not the raw
`*.github.io` URL, is what visitors and any existing links should
resolve to.

## Learn more

[Astro documentation](https://docs.astro.build)