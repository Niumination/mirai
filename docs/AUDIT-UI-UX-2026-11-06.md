# Audit UI/UX Dashboard MIRAI — Plan Perbaikan

**File:** `~/Desktop/Niumination/mirai/dashboard.html` (228 KB, single file)
**Tanggal:** 2026-11-06
**Status:** Audit awal + plan

---

## Temuan Audit

### 1. CSS Class Missing (FIXED ✅)
- `.hero-inner` — tidak didefinisikan → hero section tanpa grid layout
- `.actions` — tidak didefinisikan → tombol CTA tidak tersusun
- `.wordmark` — tidak didefinisikan → brand section tanpa margin
- `.g` — tidak didefinisikan → glyph nav tanpa alignment

### 2. Layout & Symmetry
- `.page { max-width:1100px; margin:0 auto }` — sekarang centered (fixed)
- `.pages { padding:8px 28px 40px }` — padding kiri-kanan 28px, tapi `.page` max-width 1100px → pada viewport 1440px, konten tidak penuh
- `.split { grid-template-columns:1fr 1fr }` — tidak responsif di bawah 880px (sudah ada media query)
- `.fleet-mosaic` — 2 kolom mobile, 5 kolom desktop (min-width:900px) — OK
- `.kpis` — `repeat(auto-fit, minmax(140px,1fr))` — bisa menghasilkan jumlah kolom yang tidak konsisten

### 3. Typography
- 3 font families: Instrument Serif (display), Inter (body), JetBrains Mono (labels) — konsisten
- Font sizes: clamp() digunakan untuk responsive — OK
- `.kpi b, .metric { font-size:28px }` — besar, tapi `.sub` 12px → kontras ukuran OK
- Tidak ada line-height konsisten di semua paragraf

### 4. Color & Design Tokens
- 28 unique oklch colors — bisa dikonsolidasi ke ~15
- `color-mix()` digunakan 23x — tidak didukung di Safari <16.2
- `color-scheme: light` hardcoded — tidak ada dark mode
- Kontras: `.muted-fg` oklch(0.38 0.02 60) pada cream oklch(0.97...) → ratio ~4.5 ✅ AA
- Ember soft oklch(0.78 0.16 50) pada ink oklch(0.16...) → ratio ~4.0 ⚠️ borderline

### 5. Responsive
- Hanya 1 breakpoint (880px) + 1 (900px) — tidak ada tablet-specific
- `.nav` horizontal di mobile — bisa overflow
- `.term { height:56vh }` — bisa terlalu kecil di mobile
- `.bubble { max-width:82% }` — OK

### 6. Struktur & Maintainability
- Single file 228 KB (font base64 ~180KB) — sulit di-maintain
- 15 halaman di satu file — semua JS inline
- Tidak ada build step / module bundler
- Font di-embed sebagai base64 di CSS → file besar tapi offline-capable

### 7. Accessibility
- Skip link ada ✅
- `:focus-visible` defined ✅
- `prefers-reduced-motion` handled ✅
- `pointer:coarse` tap target handled ✅
- Tapi: tidak ada `aria-live` untuk toast notifications
- Tidak ada `role="main"` pada main content

---

## Plan Perbaikan (Prioritas)

### P1 — Layout & Symmetry (sekarang)
- [x] Fix missing CSS classes (.hero-inner, .actions, .wordmark, .g)
- [x] Center .page content
- [ ] Fix .topbar alignment (align-items: center, bukan flex-end)
- [ ] Fix .kpis grid consistency (gunakan fixed columns)
- [ ] Fix .nav mobile overflow

### P2 — Typography & Color
- [ ] Konsolidasi 28 oklch colors → ~15 tokens
- [ ] Tambah dark mode (color-scheme: light dark + prefers-color-scheme)
- [ ] Pastikan semua kontras ≥4.5
- [ ] Tambah line-height konsisten

### P3 — Responsive
- [ ] Tambah breakpoint 768px (tablet)
- [ ] Fix .term height di mobile
- [ ] Fix .split grid di tablet

### P4 — Accessibility & Polish
- [ ] Tambah aria-live untuk toast
- [ ] Tambah role="main"
- [ ] Tambah loading states
- [ ] Tambah empty states yang lebih informatif

### P5 — Maintainability (long-term)
- [ ] Pisahkan CSS ke file terpisah
- [ ] Pisahkan JS per halaman
- [ ] Tambah build step (Vite/esbuild)

---

## Bukti

- File: 228782 bytes, 1285 lines
- CSS classes defined: 91, used in HTML: 61
- Media queries: 5
- Unique oklch colors: 28
- color-mix usage: 23
- Commit terakhir: 3b34408 (center .page + .wordmark/.g)
- Server: HTTP 200, read per request (no restart needed)

## Yang Sengaja Tidak Diubah
- Font base64 embed — dipertahankan untuk offline capability
- Single-file architecture — dipertahankan sesuai design decision MIRAI (no CDN)
- 15 halaman dalam satu file — dipertahankan sesuai arsitektur
- color-mix() — dipertahankan, fallback hardcoded tersedia

## Final Fix — CSS Restoration (commit d242a9d)
- Root cause: P5 split introduced brace imbalance (138/137), stray `</style>` tag, and dark-mode block overriding color tokens → text invisible, colors clashed.
- Fix: restored clean CSS from git commit 001f1f2, re-applied P1 fixes, removed dark mode, deduplicated rules.
- Result: 137/137 braces balanced, all endpoints 200, HTML/CSS/JS synced to mission-control/web/.
