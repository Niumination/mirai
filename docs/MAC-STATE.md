# Status Mac (terverifikasi Hermes) — bukan pekerjaan Arena

Snapshot **sebelum** workspace Arena di-download. Hermes Mac, bukan Arena, yang mengerjakan butir di bawah. Jangan diulang saat adopsi MIRAI.

Tanggal laporan: 2026-10-10.

## Selesai di Mac

### Skill — 0 duplikat

- Loader roots: **hanya** `/Users/zaryu/.hermes/skills`
- Skill terlihat: 293 · duplikat: **0** (sebelumnya 238)
- `skills.external_dirs` di-unset (satu-satunya key yang diubah)
- Mirror sempat tertinggal 2 skill (bank lebih baru) — sudah di-sync; backup config SHA `cc4e3dd6…`
- Drop mirror **tidak** dilakukan (akan kehilangan ~55 skill: bundled + `content-remotion-video`)
- Thread **804** binding: `codebase-audit` → **`code-audit`** (nama exact)
- **13 binding thread resolve**
- Bundled nyaris 4/4: apple-notes, codex, xlsx, gif-search

Arena **tetap tidak** menyentuh `~/.hermes/skills`.

### niu-mission-control — diarsipkan

- `services/` → `inactive-2026-10/niu-mission-control/`
- Repo utuh, `.git` bersih, remote `github.com:Niumination/niu-mission-control.git`, HEAD `85f9923` v4.1.1
- Gitlink 160000 + `.gitmodules` seperti submodule lain
- LaunchAgent `com.niumination.missioncontrol` **dihapus** (tidak ter-load; port 5200 kosong)
- BACKLOG + project-catalog: Active → Diarsipkan
- Commit `4def849` pushed `main`
- Cron bernama “MissionControl” = false positive (grup Telegram, bukan service)

Jangan hidupkan `:5200`. Jangan restore dari inactive kecuali pemilik minta.

### Diterima apa adanya (bukan bug)

- 9/10 thread `is_fresh_reset`, token 0; `kanban.db` tasks 0 / task_runs 0 → cockpit hari-1 kosong = jujur
- 10 persona Niumination menang; 3 generik MIRAI tidak dipasang

### Port / layanan (saat laporan)

Bebas untuk MIRAI: **8800, 8899, 5200**. Hidup: A2A 9900, 9router 20128, `ai.hermes.gateway`. Jangan sentuh.

## Belum (tunggu download workspace Arena)

Lihat `ADOPT-MAC.md`. Ringkas: `~/mirai-src` dari zip Arena → wiki lengkap + 5 cron → LaunchAgent `:8800` → yaml thread 1 Triage (izin sempit) → jangan create-fleet / plugin / mail-sweep / offsite.

Memory Hermes Mac sempat penuh (tulis 4× gagal); temuan ada di skill `mirai-mission-control-adoption`. Paket Arena ini adalah sumber langkah apply, bukan pengulangan fix skill.
