---
name: mirai-window
description: Jendela MIRAI poros A. Pakai saat UI dashboard, i18n, mosaic 10 kursi, wiki/cron. Jangan kota 3D, jangan niu-mc :5200, jangan tulis config.yaml Hermes.
---

# Jendela MIRAI (poros A)

- Satu file self-contained: `mission-control/web/dashboard.html` (+ salinan root). Tanpa CDN.
- Palet **ink / krim / bara**. Bukan ungu, bukan kota neon, bukan ORB.
- Permukaan: Status, 10 kursi, obrolan, jadwal, kesehatan, berkas, integrasi, pengaturan. Halaman lain `hidden`.
- i18n default ID, switch EN (`localStorage mirai.lang`). Verb CLI Inggris.
- Avatar: bust paket `web/avatars/{kode}.png` (10 file). **Jangan regenerate** kecuali user minta PNG baru.
- Off-limits: gateway, 9router, A2A, SOUL, plugin Telegram, create-fleet.
- `config.yaml` menang. Jangan push kecuali diminta.
