---
name: mirai-console-html
description: Konsol dashboard.html self-contained. Pakai saat UI Mission Control, i18n, mosaic kru.
---

# Console HTML

- Satu file: `mission-control/web/dashboard.html` (+ salinan root `dashboard.html` jika ada). **Tanpa CDN.**
- Font inline (Instrument Serif, Inter, JetBrains Mono). Palet oklch ink / cream / ember / cyan.
- i18n: default **id**, switch EN, `localStorage mirai.lang`. Verb CLI tetap Inggris.
- 15 halaman, ~54 route, perilaku API tidak diubah saat rombak visual.
- Kartu kru: inisial / mosaic 2-huruf. Jangan generate PNG avatar.
- Preview statis: `mission-control/web/ui-preview.html` (tanpa backend).
- Preview in-app tidak load jaringan; jangan andalkan stylesheet eksternal.
