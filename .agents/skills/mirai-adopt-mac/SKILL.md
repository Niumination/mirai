---
name: mirai-adopt-mac
description: Adopsi paket MIRAI di Mac Hermes. Pakai saat install, LaunchAgent, config.yaml, fleet, cron, atau skill Hermes.
---

# Adopsi Mac

- Target **Darwin**. Jangan kirim unit systemd.
- Branding **MIRAI**. Port Mission Control **:8800**. Jangan hidupkan niu-mc `:5200`.
- Python LaunchAgent: `/usr/bin/python3` (3.9.6), label hanya `com.mirai.*`.
- `config.yaml` menang. **Jangan** `create-fleet.sh` / `install-habits.sh`. Plugin Telegram **OFF**. `profile_routes` off.
- Yaml thread **1** boleh Triage. 9 thread lain + `profile_routes` tidak ditulis.
- Off-limits: gateway, 9router `:20128`, A2A `:9900`, SOUL.md.
- Skill duplikat = urusan internal Mac. **Jangan** sunting `~/.hermes/skills`.
- Wiki path: `$HOME/Desktop/Niumination/wiki`. Cron wiki **5** job; jangan mail-sweep/offsite.
- Reload LaunchAgent **dari luar** proses gateway.
- Cockpit boleh kosong jujur. Jangan seed misi palsu.

Sumber keputusan: `docs/ADOPT-MAC.md`, `docs/DEPLOY-MAC.md`, `docs/TOPIK-NIUMINATION.md`.
