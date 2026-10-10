# Tahap 2 (Arena) — health Mac, roster 10 topik, i18n

Diterapkan di workspace; Hermes Mac pull `Niumination/mirai` lalu **reload LaunchAgent dari Terminal luar gateway** (jangan bootstrap dari dalam pohon gateway).

## Health

- `kern.boottime` + fallback `uptime` → cek “Machine up over an hour” tidak lagi `unknown` di Darwin 26.
- Cron ticker: `~/.hermes/cron/ticker_heartbeat` **atau** heartbeat di `Desktop/Niumination/wiki/_wiki-health.md` (jendela 40 menit, karena dropbox `*/30`).
- Profile `default`: `state.db` aneh ≠ unreachable. Unreachable hanya jika home tidak terbaca.
- `MIRAI_DIR` otomatis ke `Desktop/Niumination/mirai` jika folder itu ada.

## Roster

`GET /api/agents` menambah persona **`kind: topic`** dari `~/.hermes/config.yaml` `channel_prompts` (stdlib, tanpa PyYAML). Tidak membuat profile Hermes.

Kode: TR/RS/BD/QA/KR/SB/AS/CR/ED/OR untuk 1,802,803,804,1172,7402,8853,12595,12707,13902.

Tanpa `channel_prompts` di yaml (uji sandbox) daftar tetap seperti dulu.

## i18n

Console: default **id**, tombol ID/EN di kaki rail, `localStorage mirai.lang`. Nav 15 halaman + grup + KPI. Bukan setiap toast. Wiki :8899 belum (LaunchAgent belum ada di Mac).

## Belum

10 avatar donghua; i18n wiki page; :8899.
