# Riset skill untuk menyempurnakan MIRAI (di Arena dulu)

Tanggal: 16 Oktober 2026. **Tidak dipasang ke Mac / `~/.hermes`.** Bank 238 Niumination tetap di ekosistem; di sini hanya **daftar yang relevan** + keputusan pakai/tolak.

Sumber dicek: GitHub `anthropics/skills`, `vercel-labs/agent-skills`, `niumination/ecosystem-config`, direktori komunitas (agentskills.io, awesome-agent-skills). Autoskills midudev **tidak** dipakai (keputusan lama).

---

## Apa yang MIRAI butuhkan (filter)

Jendela poros A: HTML satu file, tanpa CDN, token ink/krim/bara, 10 kursi jujur, i18n ID/EN, baca Hermes tanpa menulis config. Bukan kota 3D, bukan Next.js, bukan plugin Telegram.

Skill lolos jika: UI operate, a11y gelap, i18n, audit UI, skill-authoring, atau status/observability **tanpa** menyentuh gateway.

---

## A. Resmi & populer (luar)

| Skill | Sumber | Untuk MIRAI | Keputusan |
| --- | --- | --- | --- |
| **frontend-design** | [anthropics/skills](https://github.com/anthropics/skills/tree/main/skills/frontend-design) | Arah visual, anti-slop, palet tegas | **Pakai** — sudah selaras brief; jangan ganti Inter jika template wiki memakai itu |
| **web-design-guidelines** | [vercel-labs/agent-skills](https://github.com/vercel-labs/agent-skills/blob/main/skills/web-design-guidelines/SKILL.md) | Audit UI: fokus, form, gerak, i18n, tema | **Pakai giliran berikutnya** — review `dashboard.html` baris per baris |
| **webapp-testing** | [anthropics/skills](https://github.com/anthropics/skills/tree/main/skills/webapp-testing) | Cek halaman render, bukan hanya `/api/ping` | **Pakai** setelah UI stabil (di Arena, bukan Mac) |
| **theme-factory** | anthropics/skills | Variasi tema | **Hati-hati** — jangan spawn palet baru; ink/krim/bara terkunci |
| **brand-guidelines** | anthropics/skills | Konsistensi merek | **Pakai ringan** — MIRAI + Niumination, bukan niu-mc |
| **web-artifacts-builder** | anthropics/skills | Artifact React/bundler | **Tolak** untuk konsol — bertentangan self-contained |
| **skill-creator** | anthropics/skills | Menulis SKILL.md proyek | **Pakai** jika kita pecah skill `mirai-console` sendiri |
| **docx/pdf/xlsx/pptx** | anthropics/skills | Dokumen Office | Tidak untuk UI jendela |
| Koleksi 100+ “awesome” | seb1n, VoltAgent, ComposioHQ | Observability, HITL, red-team | **Pinjam ide**, jangan clone bank |

Direktori: [agentskills.io](https://agentskills.io), [philipbankier/awesome-agent-skills](https://github.com/philipbankier/awesome-agent-skills). Standar = folder + `SKILL.md`.

---

## B. Bank Niumination (sudah punya, jangan disalin massal ke Arena)

| Skill | Path di ecosystem-config | Untuk MIRAI |
| --- | --- | --- |
| **frontend-design** | `skills/design/frontend-design/` | Sama dengan Anthropic (fork) |
| **impeccable** | `skills/design/impeccable/` | Mode **Operate** + polish/quieter — pas untuk dashboard |
| **dark-theme-a11y** | `skills/design/dark-theme-a11y/` | Fokus, contrast, reduced-motion — **wajib** |
| **accessibility** | `skills/design/accessibility/` | WCAG pola |
| **niu-mission-control-ui** | `skills/ecosystem/niu-mission-control-ui/` | **Hanya** a11y/SEO; **bukan** ORB/:5200 |
| **hermes-uiux-technical** | `skills/ecosystem/hermes-uiux-technical/` | Baca jika ada pola Hermes UI; jangan tulis config |
| **web-dashboard-maintenance** | `skills/software-development/web-dashboard-maintenance/` | Cache-bust, jangan klaim “sudah” tanpa reload |
| **pemdi-uiux-refinement** | software-development | Portal dinas — tone pemerintahan, bukan neon |
| **live-ui-audit** | software-development | Audit visual vs API |
| **mirai-mission-control-adoption** | ecosystem | Sudah dipakai di Mac; **jangan ulang** di Arena sebagai apply |
| remotion / hyperframes / comfyui / three.js gamedev | creative / gamedev-skills | **Tolak** untuk jendela |

---

## C. Yang sengaja tidak diambil

- Autoskills / npx skills midudev  
- Skill yang menghidupkan plugin Telegram, create-fleet, MCP berbayar  
- Game/three.js “Agent City”  
- Menyalin 238 skill ke `mirai/.agents/skills/` (melanggar one-home + merusak workspace ramping)

Tempat skill proyek MIRAI jika nanti ditulis: **`mirai/.agents/skills/` saja**.

---

## D. Urutan pakai di Arena (usulan, belum eksekusi)

1. **vercel web-design-guidelines** pada `mission-control/web/dashboard.html` (fokus, 44px sentuh, i18n string sisa Inggris, kontras mosaic).  
2. **impeccable quieter + layout** — kurangi hero/KPI berlebih, mosaic 10 kursi prioritas.  
3. **dark-theme-a11y** — verifikasi `:focus-visible` yang baru dipasang.  
4. **webapp-testing** — 8 halaman nav terlihat, hidden tidak di menu.  
5. Baru tulis **satu** skill proyek `mirai-window` (poros A + larangan) lewat skill-creator — supaya giliran UI tidak mundur ke paket 15 halaman.

---

## E. Penyedia vs “banyak bintang”

Bintang GitHub ≠ cocok MIRAI. `frontend-design` populer justru sering mendorong font aneh dan layout pamer; **brief Niumination menang**. Vercel guidelines lebih “operate” daripada “unforgettable landing”. Itu yang kita mau.
