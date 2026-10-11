---
name: mirai-wiki-launchd
description: Wiki markdown + wiki.sh + cron malam + launchd MIRAI. Pakai saat verb wiki, lock, dashboard :8899, plist.
---

# Wiki dan launchd

- Skeleton → `$HOME/Desktop/Niumination/wiki` (bukan `~/wiki` generik).
- Perintah `wiki` 9 verb; lock = `mkdir` (macOS tidak punya `flock`).
- Dashboard wiki `:8899`. Cron malam **5** job; **jangan** `wiki-mail-sweep` / `wiki-offsite`.
- Skill wiki Hermes hanya ke profile **default**.
- LaunchAgent baru hanya `com.mirai.*`. Jangan sentuh `ai.hermes.*` / `com.niumination.*`.
- Reload plist dari shell di luar gateway.
