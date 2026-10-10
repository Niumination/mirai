# MIRAI — arsitektur

Tiga lapis, dibangun berurutan, masing-masing berguna sendiri dan menjadi prasyarat
lapis berikutnya.

```
                        ┌─────────────────────────────────────────────┐
                        │      MIRAI Mission Control  (port 8800)     │
                        │  satu proses Python: API + dashboard        │
                        │  membaca ~/.hermes, menulis hanya data-nya  │
                        └───────────────┬─────────────────────────────┘
                                        │
              ┌─────────────────────────┼──────────────────────────┐
              │                         │                          │
     ┌────────▼────────┐      ┌─────────▼─────────┐      ┌─────────▼────────┐
     │  fleet           │      │  wiki              │      │  standing orders │
     │  Executor + 3    │      │  ~/wiki            │      │  cron Hermes     │
     │  profil Hermes   │      │  hanya lewat       │      │  dropbox 30 mnt  │
     │  SOUL masing2    │      │  perintah `wiki`   │      │  librarian 02:30 │
     └────────┬─────────┘      └─────────┬──────────┘      │  lint      02:50 │
              │                          │                 │  snapshot 02:20/03:10
              │                          │                 │  offsite   03:40 │
              └──────────────┬───────────┘                 └──────────────────┘
                             │
                  ┌──────────▼───────────┐        ┌────────────────────────┐
                  │  Grup Telegram       │        │  dashboard wiki :8899  │
                  │  satu topik per agen │        │  drop door, lint, snap │
                  └──────────────────────┘        └────────────────────────┘
```

## Lapis 1 — Memori (wiki)

Markdown biasa di `~/wiki`, karena riwayat chat diringkas hilang dan ini tidak.

- `processed/personal|business|research|concepts/` — yang **ditulis** agen.
  `raw/` — sumber verbatim, tidak pernah diedit, jadi tiap klaim bisa dicek.
- `index.md` (katalog, dibaca PERTAMA), `log.md` (diary append-only), `WIKI.md` (rulebook).
- **Satu pintu masuk: perintah `wiki`.** 8 verb, satu `flock`, dan penolakan yang
  melindungi korpus: halaman berubah sejak dibaca, nama sudah ada di folder lain,
  raw slug sudah pernah difile, halaman belum ada tidak bisa dilog.
- `raw/_inbox` diisi Telegram, dashboard drop door, atau tangan; job 30 menit
  mengurasnya: `_inbox → _working → _done / _failed`, dan run yang mati diadopsi.

## Lapis 2 — Fleet (siapa yang bekerja)

Profil Hermes persisten, bukan asisten instan. Executor = profil default =
orkestrator; Research, Content Writer, Developer = profil nyata dengan memori,
workspace dan identitas sendiri di SOUL.md.

Tiap SOUL memuat tiga blok yang sama, **verbatim**: kebiasaan wiki, aturan
"mulai dengan nama owner", dan fact-vs-inference. Bagian `## The team` yang sama
membuat mereka saling tahu, dan satu kalimat batas membuat masing-masing menyebut
rekan yang tepat daripada mengerjakan di luar keahliannya.

Telegram adalah antarmukanya: satu topik per agen, dirutekan plugin yang tinggal
**di samping** Hermes (`~/.hermes/plugins/`), bukan di dalamnya, supaya update
Hermes tidak menghapusnya.

## Lapis 3 — Mission Control (jendela)

Satu proses Python, stdlib saja, bind 127.0.0.1:

- **Membaca Hermes, tidak pernah menulis**, dengan tepat tiga pengecualian:
  cron store (CLI-nya sendiri), file editable (SOUL.md, config.yaml,
  memories/USER.md + MEMORY.md) di belakang backup, dan login agent baru.
- **State-nya sendiri** di `~/mirai/data/mirai.db` (SQLite WAL).
- **Front end-nya** satu file di `~/mirai/dashboard.html`, dilayani proses yang
  sama, jadi mustahil halaman hidup sementara API mati.
- 15 surface: cockpit, agents, deploy, city, missions, chat, docs, schedule,
  health, files, terminal, voice, hand mode, integrations, settings.

## Kenapa Mac mengubah beberapa hal

Pack sumbernya ditulis untuk Linux:

| Di pack | Di sini |
| --- | --- |
| `systemd --user` unit | launchd LaunchAgent (`KeepAlive` = `Restart=always`) |
| `/proc/stat`, `/proc/meminfo` | `ps`, `vm_stat`, `sysctl` (jalur Linux tetap ada untuk container) |
| `ss -ltnp` cari pemilik port | `lsof -nP -iTCP:<port> -sTCP:LISTEN` |
| `loginctl enable-linger` | `RunAtLoad` + sesi user LaunchAgent |
| `apt install python3-venv` | python3 bawaan macOS; Homebrew untuk tool opsional |
| `pkill -f "server.py 8800"` | jangan pernah: itu mencocokkan shell tempat kamu mengetiknya dan mematikan sesimu. `restart.sh` mencari pemilik port |

Selebihnya — path, kontrak, kosakata penolakan, shape respons — mengikuti pack
apa adanya, karena front end dashboard-nya ditulis terhadap kontrak itu.

## Aturan yang menyatukan sistem

1. **Tidak pernah 0.0.0.0.**
2. **Satu penulis.** Tulisan wiki lewat perintah `wiki` (lock + halaman + index + log
   dalam satu operasi).
3. **Buktikan dengan melihat.** Tiap langkah deploy berakhir dengan perintah yang
   keluarannya adalah buktinya.
4. **Tidak ada yang berbiaya atau keluar rumah** tanpa izin eksplisit.
