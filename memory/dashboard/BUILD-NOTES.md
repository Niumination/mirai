# How wiki-page.html was made (and how to make it again)

The dashboard page ships as **one file with no network calls**: no CDN, no fonts from a
server, no icon library fetched at runtime. Open it from disk and it still looks right —
which matters because it is also what you see when your Mac's wifi is off, and because a
page that phones a CDN tells that CDN every time you look at your own notes.

Three things had to be replaced to get there. This file records exactly what with, so the
next person (or the next you) does not have to reverse-engineer it.

## 1. Tailwind — the Play CDN became a real build

The page's markup uses Tailwind utility classes. The CDN builds the CSS in your browser
at load time; off-network there is nothing to build with, so the utilities simply do not
exist and the page collapses to its custom CSS.

    cd /tmp && mkdir tw && cd tw
    npm i tailwindcss@3.4.17
    # config: copy the page's own `tailwind.config = {...}` object into tailwind.config.js
    # (module.exports = {...}), add:  content: ['<path>/wiki-page.html']
    printf '@tailwind base;\n@tailwind components;\n@tailwind utilities;\n' > in.css
    npx tailwindcss -c tailwind.config.js -i in.css -o out.css --minify

Result: ~17 KB of CSS, and it is the *same config* the CDN was handed, so the classes that
worked before still work, and the ones that did not (see below) still do not.

The `<style>` sits exactly where the `<script src="cdn.tailwindcss.com">` used to sit:
before the page's own `<style>` block. That keeps the cascade in the same order it had
when the CDN injected its stylesheet at parse time.

**Known and deliberate:** Tailwind v3 cannot apply an opacity modifier to a colour that is
written as an `oklch()` string, so classes like `bg-cream/5` and `text-cream/50` generate
nothing — under the CDN either. That is why the page looks the way it looks today, and the
build reproduces it rather than "fixing" it. If you ever want those to work, define the
colours as `oklch(... / <alpha-value>)` in the config.

## 2. Fonts — inlined as woff2 data URIs

    # ask Google for the CSS with a modern user-agent (woff2 + unicode-range subsets),
    # for variable fonts where they exist: Inter 300..900, JetBrains Mono 400..600
    curl -A '<a Chrome UA>' 'https://fonts.googleapis.com/css2?family=Inter:wght@300..900&...' > gf.css
    # keep only the latin subset, then inline each woff2 as a data: URI

Four files, ~112 KB raw, ~149 KB as base64 (`@font-face{... src:url("data:font/woff2;base64,...")}`):
Instrument Serif regular + italic, Inter variable, JetBrains Mono variable. Latin subset
only — that covers Indonesian and English text; Latin-extended (Cyrillic, Greek, Vietnamese
ranges) was dropped on purpose to keep the page one file of reasonable size.

## 3. Icons — 21 of Lucide's 2 133, plus a shim

    npm i lucide-static@latest         # the SVGs
    node -e '...'                      # collect every name the page uses, copy the inner SVG

The page calls `if (window.lucide) lucide.createIcons()` in ~14 places. Rather than edit
every call site, the build defines `window.lucide` with a `createIcons()` that has the same
behaviour: it finds `[data-lucide]`, builds the `<svg>`, copies the element's attributes
(class, size) onto it and swaps it in. The call sites did not change.

Names are collected two ways so nothing is missed: every `data-lucide="..."` in the markup,
**and** every quoted kebab-case string in the page that matches a real Lucide filename (that
is how `circle-dashed` and `file-cog` were found — they only ever appear as arguments).

## 4. The bug that was in the file all along

Every `<script>` in the page carried Cloudflare's

    type="36bf5ad56112f4ea6974400d-text/javascript"

That is not a JavaScript MIME type, so a browser treats the element as a **data block and
does not execute it**. All four scripts were inert: no Tailwind, no icons, no data, no page
render. The template the design came from was saved from a live site and carries the same
attribute, so this was inherited rather than invented — and it is invisible in a static
review, which is exactly why the page "worked" in every test that only fetched it.

The build strips those attributes (all four), deletes the dead `/cdn-cgi/…/rocket-loader.js`
tag, and — because the page's own JavaScript had never actually run — fixes the one syntax
error that had been hiding behind the dead script: a single-quoted string with a real
newline inside it (`'# ' + slug + '\n\nCould not load this page: '`).

Verified after: the page's script parses (`node --check`), and a jsdom run boots the page
with its APIs stubbed — 23 icons become `<svg>`, the tree renders, a page body loads, no
errors thrown.

## Rebuilding, in one place

The build helpers are not part of the package (they need npm and the network); this file is
the record. If you change the page and want a new self-contained build, repeat the three
sections above and keep the two invariants:

1. `<style>` for Tailwind goes where the CDN script was — before the page's own `<style>`.
2. The page must contain no `http(s)://` reference in `src=`/`href=`. Check with:

       grep -o 'src="http[^"]*"\|href="http[^"]*"' wiki-page.html   # must print nothing
