---
name: mirai-python-stdlib
description: Backend Mission Control Python 3.9 stdlib. Pakai saat mengedit server/, route API, health Darwin, roster.
---

# Mission Control — Python stdlib

- Hanya stdlib 3.9. Jangan pip / venv di deliverable Mac.
- Health: Darwin (`sysctl`, `vm_stat`, `df`), bukan `/proc`.
- Roster: 10 kursi `kind: topic` (bukan profile fleet). Avatar pack **dibatalkan** — jangan PNG kru, jangan `GET /crew/`.
- API topik: TR/RS/BD/QA/KR/SB/AS/CR/ED/OR ↔ thread 1,802,803,804,1172,7402,8853,12595,12707,13902.
- Ticker wiki: hermes cron **atau** `_wiki-health.md` < 40 menit.
- Jangan `create-fleet`. Install: `mission-control/scripts/install-mac.sh`.
- Uji: `mission-control/tests/mac-verify.sh` (harapan 22/0 di Mac).
