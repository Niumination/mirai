# Agent notes — MIRAI

Stack: Python 3.9 **stdlib only** (Mission Control), HTML/CSS/JS satu file tanpa CDN, wiki markdown + `wiki.sh`, LaunchAgent `com.mirai.*` di Darwin. Bukan Next.js / Node.

**Jangan** pakai `npx autoskills` sebagai sumber utama: CLI butuh Node ≥22.6 dan registry-nya frontend/cloud (React, Next, Tailwind…). Repo ini tidak punya `package.json`. Skills relevan ada di `.agents/skills/` (proyek), **bukan** `~/.hermes/skills`.

Baca `docs/ADOPT-MAC.md` sebelum mengubah Mac. Larangan: `create-fleet.sh`, `install-habits.sh`, gateway/9router/A2A, SOUL, plugin Telegram, cron mail-sweep/offsite.
