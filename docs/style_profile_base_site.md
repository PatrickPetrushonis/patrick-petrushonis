# Style profile: base site

Profile for `scss_style_guide.md` (§16). It holds every fact specific to the base site (`patrick-petrushonis`, Astro). A rule in the core guide refers here; the core names no file, class, or value of this site. `scripts/check_styles.py --profile <this file>` reads the tables below and compares them to the code (15.7).

*Last reviewed: 2026-11-26. Stack: Dart Sass module system, loaded through `src/styles/main.scss` from `src/layouts/Layout.astro`. Markup is Astro (`class="…"`). Built-in modules load only with `@use`, and only Dart Sass supports that ([Sass docs](https://sass-lang.com/documentation//modules/math)).*

---

## 0.13 Code outside the styles

Behavior of these is Unknown until read (0.13): `utils/*`, `lib/prose.js`, content files.

## 1.1 Layout

```
src/styles/
├── main.scss                 entry: the only file that loads base/ and components/ partials
├── utilities/
│   ├── _index.scss           forwards functions, mixins, variables
│   ├── _variables.scss       every token
│   ├── _functions.scss       color(), theme()
│   ├── _mixins.scss          breakpoint(), lift-on-hover, social-icon(), rule-icon()
│   ├── _themes.scss          emits the theme custom properties
│   └── _helpers.scss         single-purpose utility classes
├── base/
│   ├── _base.scss            element defaults, page shell, focus, reduced motion
│   └── _grid.scss            12-column flex grid
└── components/
    ├── _header.scss  _theme-toggle.scss  _footer.scss  _buttons.scss
    └── _sections.scss  _about.scss  _projects.scss  _prose.scss
```

## 1.4 Reference site

None. This is the reference site for other profiles.

## 2.2 Token reference

| Group | Tokens |
|---|---|
| Palette | `$color-map`: `primary` (`light`, `mild`, `mid`, `dark`), `gray` (`light`, `mild`, `mid`, `dark`, `jet`) |
| Breakpoints | `$small-screen` 768px, `$medium-screen` 1024px, `$large-screen` 1366px |
| Font | `$font-family` |
| Spacing | `$space-xs` 5.5px, `$space-sm` 11px, `$space-md` 22px, `$space-lg` 44px |
| Fixed-bar geometry | `$header-height` 61px, `$header-height-mobile` 65px, `$footer-height` 55px, `$return-top-offset` |
| Motion | `$transition` (`all 0.3s ease-out`) |
| Grid | `$grid-columns` 12, `$grid-gutter` |
| Long-form reading | `$prose-measure` 68ch, `$prose-font-size` 18px, `$prose-line-height` 1.7 |
| Layering | `$header-container` (z-index) |

## 2.3 Derived values

`$header-height` equals the header's `.button` box (16px line-height + 2 × `$space-sm` padding = 38px) + 2 × `$space-sm` margins + the 1px border. `$header-height-mobile` equals the hamburger (24px) + 2 × 20px margins + the border. A change to `.button` padding, line-height, or header margins updates the matching token in the same change.

Script constants that mirror a CSS value: the offset `77` in `smoothScrollTo` and `initHashNavigationOnLoad` (`utils/scroll.js`), in the `smoothScrollTo` call in `utils/header.js`, and in the `initHashNavigationOnLoad(77)` call in `Layout.astro` mirrors the header geometry.

## 3.1 Brand elements

`color()` applies to `.header-container`, `.footer-container`, anything inside them, and the brand fills `.button` and `.project__link`.

## 3.2 Roles

| Role | Purpose | Light | Dark |
|---|---|---|---|
| `surface` | Page background; rule-icon knockout patch | gray-light `#f5f5f5` | gray-jet `#212121` |
| `text` | Body text | gray-jet `#212121` | gray-light `#f5f5f5` |
| `text-muted` | Secondary text | gray-mid `#616161` | gray-mild `#bdbdbd` |
| `link` | Link text | primary-mild `#006cb2` | primary-light `#009bff` |
| `focus` | Focus outline | primary-mild `#006cb2` | primary-light `#009bff` |
| `border` | Structural lines (rule, blockquote, details box) | gray-mid `#616161` | gray-mid `#616161` |
| `border-subtle` | Dividers (list rows, prose `hr`, nav top rule) | gray-mild `#bdbdbd` | gray-dark `#424242` |
| `border-strong` | Borders that signal state | gray-mid `#616161` | gray-mild `#bdbdbd` |
| `fill-strong` | Solid circular fills | gray-jet `#212121` | gray-mid `#616161` |

## 3.4 Theme mechanics

An `is:inline` script in `src/layouts/Layout.astro`'s `<head>` sets `data-theme` before first paint ([source](https://dev.to/sourcier/building-a-darklight-theme-toggle-in-astro-5c7l)). `src/components/ThemeToggle.astro` renders the control; `src/utils/theme.js` flips the attribute and saves the choice. `Layout.astro` and `utils/theme.js` hard-code the same `localStorage` key (`theme`).

## 3.5 Contrast

**3.5.1** Each role meets its threshold against `surface` in both themes:

| Role | Required | Light | Dark |
|---|---|---|---|
| `text`, `text-muted`, `link` | 4.5 | 14.77, 5.68, 5.09 | 14.77, 8.57, 5.47 |
| `focus`, `border-strong`, `fill-strong` | 3 | 5.09, 5.68, 14.77 | 5.47, 8.57, **2.60** |
| `border`, `border-subtle` | none (structural) | 5.68, 1.72 | 2.60, 1.60 |

Light text on the brand bar (`#f5f5f5` on `#002e4c`) is 12.88:1.

Exempt role: dark `fill-strong` (2.60:1 against `surface`), listed in §15.9. The arrow icon's contrast against the fill is set in `icon-arrow-up.svg`, which the checker does not read.

## 4.3 Image mixins

| Mixin | Path built |
|---|---|
| `social-icon` | `/app/img/logo-<name>.svg` |
| `rule-icon` | `/app/img/rule-<name>.svg` |

## 7.1 Rows outside the grid

`.chapter__nav` is a flex row with `gap` and `$space-*`. `.flex__small--alt` on a `.flex-content` container stretches its items.

## 8.1 Coupled sub-blocks

`.nav-icon` in `_header`, `.social-icon*` in `_footer`, `.chapter*` in `_prose`.

## 8.2 Hover and transitions

Project thumbnails use `scale(1.05, 1.05)` on hover. `.project__details` animates only margin and padding over 0.5s; that is why it does not use `$transition`.

## 9.2 Long-form content

The scoped block is `.prose`, in `components/_prose.scss`. Rendered markdown (`<Content />`) is wrapped in it.

| Property | Value |
|---|---|
| Measure | `max-width: $prose-measure`, centered |
| Size | `$prose-font-size` |
| Line height | `$prose-line-height`, unitless |
| Alignment | Left; no justification |
| Links | Underlined, `font-weight: inherit`, `text-underline-offset: 0.15em` |
| `h2`–`h6` | Left-aligned, `$space-lg` above, `$space-sm` below |
| Blockquote | 3px left rule in `border`, `$space-md` indent |
| `hr` | 1px rule in `border-subtle`, `$space-lg` vertical |
| Lists | `$space-lg` left padding |
| Images | Block, centered, `max-width: 100%` |

Chapter metadata is `.chapter__meta` (14px, `text-muted`, centered). Chapter navigation is `.chapter__nav` (flex, `gap: $space-md`, `border-subtle` top rule).

## 11.5 Control sizes

The theme toggle is 38px (wide) and 40px (narrow); return-to-top is 44px; the hamburger (28 × 24px) is exempt, because its size sets `$header-height-mobile` (2.3).

## 12.1 Layout components and generated rule

The layout component is `Layout` (`src/layouts/Layout.astro`). The page-section component is `PageSection`, rendering `.section__container > .section__content`. The one generated rule is `<style id="footer-padding-style">`, filled by `initFooterPadding`. Class names in content files (`set:html` fragments, markdown) count as markup uses.

## 12.2 Script-affected selectors

| Selector | Set by | On | Styled in |
|---|---|---|---|
| `[data-theme]` on `<html>` | `Layout.astro` inline script; `theme.js` | `<html>` | `utilities/_themes.scss`, `components/_theme-toggle.scss` |
| `.fixed` | markup (hard-coded) | `.header-container` | `_header.scss` |
| `.header-container--slim` | `header.js` (`initScrollThresholdClass`, 100px) | `.header-container` | `_header.scss`, `_theme-toggle.scss` |
| `.show-nav` | `header.js` (checkbox change) | `#nav-list` | `_header.scss` |
| `.is-visible` | `scroll.js` (`initScrollThresholdClass`, 100px) | `.button__return-top` | `_buttons.scss` |
| `.selected` | `tabs.js` | `.project__link`, `.project__details` | `_projects.scss` |

Exempt from the `is-` prefix (4.1.2): `.fixed`, `.show-nav`, `.selected`, `.header-container--slim`.

## 12.3 Components and hooks

| Partial | Classes | Appearance |
|---|---|---|
| `_header` | `.header-container`, `.header-controls`, `.header-logo`, `.header-controls__nav-toggle`, `.nav-icon` | Brand bar |
| `_theme-toggle` | `.theme-toggle`, `.theme-toggle__icon`, `--moon`, `--sun` | Brand bar |
| `_footer` | `.footer-container`, `.footer-controls`, `.footer-signature`, `.social-icon__container`, `.social-icon`, `.social-github`, `.social-linkedin` | Brand bar |
| `_buttons` | `.button`, `.button__return-top` | Brand text; themed fill on return-to-top |
| `_sections` | `.section__container`, `.section__content`, `.section__title`, `.section__rule--about`, `.section__rule--projects` | Themed |
| `_about` | `.about__portrait` | Themed |
| `_projects` | `.project__item`, `.project__link`, `.project__image`, `.project__details`, `.project-tab__radio` | Brand fill; themed borders |
| `_prose` | `.prose`, `.chapter__meta`, `.chapter__nav`, `.chapter__nav-link--next`, `.chapter-list` | Themed |
| `_grid` | `.flex-content`, `.flex__small--N`, `.flex__large--N`, `.flex__small--alt` | Layout only |
| `_base` | element rules, `.main-container`, `.main-content` | Themed |
| `_helpers` | `.mobile-only`, `.hide-on-mobile`, `.hide-on-mobile__inline`, `.hide`, `.center`, `.marg-{side}-0`, `.pad-{side}-0` | None |

Markup hooks with no rule: `.content`, `.project-tabs`.

The `.content` hook wraps the page slot in `Layout.astro`. The `.project-tabs` hook is the container that `utils/tabs.js` queries. Brand bars: `_header`, `_theme-toggle`, `_footer`.

## 12.4 Runtime class names

Does not apply. Astro markup writes `class` attributes; no class string is built at runtime.

## 15.9 Checker settings

| Key | Value |
|---|---|
| `stack` | Astro; Dart Sass |
| `markup extensions` | `.astro`, `.md`, `.mdx`, `.html`, `.js`, `.ts` |
| `markup roots` | `.` |
| `theme key files` | `layouts/Layout.astro`, `utils/theme.js` |
| `exempt roles` | `dark:fill-strong` |
| `!important files` | `base/_base.scss`, `utilities/_helpers.scss` |

`theme key files`: the first file reads the key with `getItem('<key>')`; the second declares `STORAGE_KEY = '<key>'`. Paths are relative to `src/`. Markup roots are relative to `src/`; `.` is `src/` itself.

---

# References

- Sass interpolation, including custom property values: <https://sass-lang.com/documentation/interpolation/>
- Sass math module (`math.div`, `math.percentage`): <https://sass-lang.com/documentation//modules/math>
- Sass numeric operators: <https://sass-lang.com/documentation/operators/numeric/>
- CSS Color Adjustment Module Level 1 (`color-scheme`): <https://www.w3.org/TR/css-color-adjust-1/>
- WCAG 1.4.3 Contrast (Minimum): <https://w3c.github.io/wcag/understanding/contrast-minimum.html>
- WCAG 1.4.11 Non-text Contrast: <https://www.w3.org/WAI/WCAG22/Understanding/non-text-contrast.html>
- Sass mixed declarations (`mixed-decls`): <https://sass-lang.com/d/mixed-decls>
- Astro theme toggle with an inline head script: <https://dev.to/sourcier/building-a-darklight-theme-toggle-in-astro-5c7l>
