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

Console: default **id**, tombol ID/EN di kaki rail, `localStorage mirai.lang`. Nav 15 halaman + grup + KPI. Bukan setiap toast.

Konsol visual (arena #4, commit `1930921`): ink field, mosaic kru 2-huruf, tanpa pack avatar.

## Bukan pekerjaan ini lagi

- **Avatar 10 PNG / `/crew/`** — dibatalkan. Kartu inisial saja.
- **autoskills midudev** — tidak cocok (Node ≥22 + stack JS). Skills agen ada di `.agents/skills/` + `AGENTS.md`.

## Masih di Mac (bukan sandbox)

- Reload LaunchAgent `com.mirai.*` dari Terminal **luar** gateway; `mac-verify`.
- Wiki dashboard **:8899** + i18n halaman wiki (console sudah ID).
- Health Darwin, chat Hermes, kamera, Whisper — lihat `STATUS-UJI.md` / `HERMES-NEXT.md`.
