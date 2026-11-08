# Handoff Arena → Hermes Mac

Workspace ini **siap diserahkan**. Arena **tidak** menjalankan LaunchAgent, **tidak** menulis `~/.hermes`, **tidak** push.

Baca dulu: `ADOPT-MAC.md` (larangan), `NEXORA-PLAYBOOK.md` (F6), `NEXORA-VERIFIKASI.md`.

## Yang sudah di tree (jangan diulang sebagai “pasang NEXORA”)

- Jendela Poros A: nav tanpa chat/integrasi/deploy/tangan/kota 3D/misi/terminal/suara
- `/api/house` + `telegram_url` `t.me/c/4204696417/<thread>`
- Avatar WebP animasi + `*-still.webp` + `prefers-reduced-motion`
- `GET /api/wiki` baca-saja (`wiki_view.py`) — korpus = `roster._wiki_dir()`
- README = jendela 10 kursi, bukan fleet 3 orang
- `create-fleet.sh` / plugin: **artefak**, jangan dijalankan

## Yang Hermes Mac kerjakan (F6 saja)

1. Letakkan sumber ke `~/mirai` (bukan menimpa `config.yaml` / SOUL).
2. `bash mission-control/scripts/install-mac.sh` **hanya** `com.mirai.mission-control` (`/usr/bin/python3`).
3. Reload LaunchAgent **dari luar** gateway. Jangan `ai.hermes.*`.
4. Buka `127.0.0.1:8800` — 10 kursi, tautan Telegram, Wiki path Desktop, 5 cron.
5. `bash mission-control/tests/mac-verify.sh` — mail-sweep **harus tidak** ada.
6. Jangan `create-fleet.sh`, `install-habits.sh`, plugin ON, niu-mc `:5200`.

Bukti yang pemilik minta belakangan: screenshot 10 kursi, `GET /api/house`, `GET /api/wiki`, pack webp, ping.
