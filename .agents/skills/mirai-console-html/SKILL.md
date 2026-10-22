---
name: mirai-console-html
description: HTML dashboard MIRAI. Palet ink/krim/bara, Instrument Serif + DM Sans + JetBrains Mono, tanpa CDN. Bukan mosaic 2-huruf cyan.
---

# Konsol HTML

- File: `mirai/mission-control/web/dashboard.html`.
- CSS dari-nol (Operate). Kartu `.mosaic` **gambar bust** `object-fit:cover` + kode 2 huruf overlay, **bukan** inisial cyan.
- `seatCard` memakai `s.avatar.url`. Pustaka: `GET /api/avatars/library`. Paket: `GET /api/avatars/pack?code=xx`.
- i18n: objek `I18N` + `t()`. Tambah kunci baru di ID dan EN.
- Jangan theme-factory. Jangan web-artifacts-builder. Jangan `:5200`.
