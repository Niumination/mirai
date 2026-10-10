# Peta prompt → artifact

Tiga pack sumber (83 prompt) dikerjakan jadi kode. Tabel di bawah memetakan
**setiap** prompt. Kosakata status:

- **as-delivered** — instruksinya dijalankan apa adanya.
- **adapted** — instruksi sama, berubah karena mesinnya Mac (atau karena keputusan
  Anda: branding MIRAI, bukan NEXORA). Perubahannya disebutkan.
- **download** — tidak bisa jadi file di folder ini; itu aset produknya sendiri.
- **skipped** — tidak dikerjakan, dengan alasan.

## Pack NEXORA (46) — Mission Control

| # | Prompt | Artifact | Status |
| --- | --- | --- | --- |
| 1 | Introduce Yourself and Meet NEXORA | briefing + keputusan Anda (kode · baru · mirai) | as-delivered (nama: MIRAI) |
| 2 | Let NEXORA Interview You | pertanyaan via `ask_user` → scope terkunci | as-delivered |
| 3 | Install Permanent Operating Rules | `fleet/config/operating-rules.md` + blok di setiap SOUL | as-delivered |
| 4 | Plan the Four-Agent Fleet | `fleet/profiles/*` + `docs/00-ARSITEKTUR.md` | as-delivered |
| 5 | Create the Three Specialists | `fleet/scripts/create-fleet.sh` | as-delivered |
| 6 | Memory, Workspaces and Team Awareness | `## The team` di 4 SOUL + `proj` workspace + habits | as-delivered |
| 7 | The Project Folder and the Activity Log | `~/mirai/proj` + baris `activity.log` di SOUL | as-delivered |
| 8 | Brief Your Builder | aturan "blocked commands" (satu perintah balik, tunggu, verifikasi) | as-delivered |
| 9 | The Router | `mission-control/server/server.py` (ROUTES, ApiError, Raw/Stream, batas body) | as-delivered |
| 10 | Where Our Own State Lives | `store.py` → `~/mirai/data/mirai.db` (WAL), `secrets.env` 0600 | as-delivered |
| 11 | Prove The Floor | `mirai/_prove.sh` + hasilnya di `docs/STATUS-UJI.md` | as-delivered |
| 12 | Find Your Agents | `roster.py` (read-only, KODE 2 huruf, status, `-shm` tidak dianggap tulisan) | as-delivered |
| 13 | The Fleet Endpoint | `roster.py` → `GET /api/agents` (54 field termasuk `fleet`, `gateway`, `cron`) | as-delivered |
| 14 | Who Is Running This | `settings.py` (4 kunci tertutup, `operator_name` read-only dari USER.md) | as-delivered |
| 15 | Faces | `avatars.py` (upload id 32 hex, sniff magic bytes, 52 portrait ada di file dashboard) | as-delivered |
| 16 | One Real Turn | `chat.py` — `hermes [-p X] chat -q … -Q --source mirai -c mirai-<agent> --create-if-missing` | as-delivered |
| 17 | Remembering And Forgetting | `/api/chat/history`, `/api/chat/forget`, tabel `turns` | as-delivered |
| 18 | Attachments | `/api/chat` terima `files`, `/api/chat/file` (id 32 hex), batas 4×8 MB | as-delivered |
| 19 | A Voice On This Machine | `voice.py` (mode 1/2/3, ElevenLabs opsional, `X-Voice-Engine`) | as-delivered |
| 20 | Voice Mode | `POST /api/voice/config` + 3 mode numerik; 2/3 fallback ke lokal | as-delivered |
| 21 | What A Mission Is | `missions.py` (NX-\d{4,6}, step, batas 15–480 menit / 2–8 step) | as-delivered |
| 22 | Launching One | `POST /api/missions` + planner, mode board vs local | as-delivered |
| 23 | The Seven Verbs | `POST /api/missions/action` (approve…clear) + `stop` = reclaim→unassign→archive | as-delivered |
| 24 | Hiring | `workforce.py` (`profile create --clone`, salin auth/config/.env minus token platform) | as-delivered |
| 25 | Letting Go | `POST /api/workforce/remove` (arsip tar.gz 0600 tanpa rahasia, konfirmasi nama) | as-delivered |
| 26 | Standing Orders | `cron.py` (jobs.json object + `live`, `schedule.expr`, verb `remove`, ticker heartbeat) | as-delivered |
| 27 | The Library | `POST /api/docs/save` (`~/mirai/data/docs/<AGENT>/<tanggal>_<slug>.md` + front matter) | as-delivered |
| 28 | Writing, Deleting, Keeping | `docs.py` (delete → `docs-deleted/<stamp>_<nama>`, tanpa penghapusan permanen) | as-delivered |
| 29 | What The Box Is Doing | `health.py` (sampler 3 s, 20 check, `ps`/`vm_stat`/`sysctl`) | **adapted**: `/proc` → macOS, jalur Linux tetap ada |
| 30 | What They Said To Each Other | `traffic.py` (kanban.db mode=ro, `task_runs` terbaru, MAX_ROWS 400) | as-delivered |
| 31 | Their Files | `files.py` (4 file editable, YAML sanity, backup, mtime drift → 409) | as-delivered |
| 32 | A Real Shell | `terminal.py` (pty, ring 64 KB + seq, SSE base64 `id: seq`, kill HUP→TERM→KILL) | as-delivered |
| 33 | Prove The Backend | `_prove.sh`: semua GET + penolakan + batas 30 MB + "hanya menulis di 3 kasus" | as-delivered |
| 34 | Bring The Dashboard Down | `GET /` + `/index.html` (gzip + ETag/304, dibaca per request), `/lib/...` untuk Hand mode | **adapted**: path `~/mirai/`, bukan `~/nexora/` |
| 35 | Hand Mode's Models | `lib/mediapipe/` — 6 berkas, 30 MB, **sudah diunduh** + `SHA256SUMS.txt`; `fetch-mediapipe.sh` untuk klon dari repo | as-delivered (dijalankan sungguhan; 1 bug batas ukuran ketahuan di situ) |
| 36 | Make It Yours | `POST /api/settings` display_name + timezone; SOUL tidak disentuh (mtime dibuktikan) | as-delivered |
| 37 | Their Faces | `POST /api/avatars/set` (library/upload/reset) + `/api/avatars/file` | as-delivered |
| 38 | Palette, Layout And Type | konsol MIRAI `mission-control/web/dashboard.html` (gaya = template Anda) + pratinjau `web/ui-preview.html` | **download**: halaman jadi ±9 MB adalah aset produk; konsol pengganti saya sertakan dan uji |
| 39 | Walk Every Page | 15 halaman konsol, tiap halaman punya renderer nyata / menyebut "belum ada" | as-delivered |
| 40 | It Comes Back By Itself | `launchd/com.mirai.mission-control.plist` (KeepAlive + RunAtLoad) | **adapted**: launchd, bukan systemd |
| 41 | One Way To Restart It | `scripts/restart.sh` (pid sebelum/sesudah, `lsof`, gagal keras) | **adapted**: launchctl/lsof |
| 42 | Reachable Only By You | bind 127.0.0.1 + Host allowlist `MIRAI_HOSTS` di **Mission Control** dan dashboard wiki; `scripts/tailscale-serve.sh` (baca dulu, tolak funnel, `lsof` memastikan tak ada listener publik) | **adapted**: Tailscale sebagai proxy, tanpa funnel |
| 43 | A Lock On The Door | `gate.py` (`MIRAI_AUTH=on`, token 0600, cookie HttpOnly 30 hari dari `?k=`) + halaman sign-in sendiri + `scripts/link.sh`; dibuktikan 7 keadaan di `prove.sh` | as-delivered |
| 44 | History | tabel `turns` (source `mirai`, ms, files) + `/api/chat/history` | as-delivered |
| 45 | Keep A Copy | `scripts/backup.sh` (snapshot hard-link, restore.sh di tiap snapshot, simpan 30) | as-delivered |
| 46 | Preset Roles | `mission-control/data/roles.json` (14 role + directions) | as-delivered |

## Pack memori (26) — Agent OS wiki

| # | Prompt | Artifact | Status |
| --- | --- | --- | --- |
| 1–2 | Brief Your Builder (Hermes/Claude Code) | semua dokumen di `docs/` + aturan builder | as-delivered |
| 3 | Build the Wiki and Its Rules | `memory/wiki-skeleton/{WIKI.md,index.md,log.md}` + struktur folder | as-delivered |
| 4 | Build the Wiki Skill | `memory/skill/wiki/{wiki.sh,SKILL.md}` (8 verb, lock, penolakan) | as-delivered |
| 5 | Install the Habits | `fleet/scripts/install-habits.sh` (append verbatim + hitungan bukti) | as-delivered |
| 6 | Every Reply Starts With Your Name | blok `## Whenever you respond` di tiap SOUL | as-delivered |
| 7 | Empty Your Head Into It | `wiki file personal …` + `WIKI.md` rulebook | as-delivered |
| 8 | The Recall Test | prosedur tes di `SKILL.md` + langkah 8 `DEPLOY-MAC.md` | as-delivered |
| 9 | Their Claims Are Not Your Facts | blok fact-vs-inference (WIKI.md, SKILL.md, semua SOUL) | as-delivered |
| 10 | Install the Ingest Operation | blok INGEST verbatim di `RESEARCH-SOUL.md` **+ dicerminkan ke `WIKI.md` WORKFLOWS/INGEST** (keduanya, sesuai perintah) | as-delivered |
| 11 | Run the First Ingest | langkah-langkah ingest + `drafts/` | as-delivered |
| 12 | Teach It YouTube | `memory/skill/youtube-transcript/` (skill + skrip) | as-delivered |
| 13 | A Drop Box That Runs Itself | cron `wiki-dropbox` (30 menit, adopsi run mati) | as-delivered |
| 14 | Connect Your Mail | langkah 3b `DEPLOY-MAC.md`: `composio install` → `composio login` → `composio connect gmail --profile research` + bukti 3 subjek. Job `wiki-mail-sweep` sudah ada, menyala setelah mailbox tersambung | as-delivered (login akunmu di sisi kamu) |
| 15 | Turn the Inbox Into Memory | blok `## MAIL SWEEP` verbatim di `RESEARCH-SOUL.md` (pindahkan kalau profil mail-nya lain) + job `wiki-mail-sweep` | as-delivered |
| 16 | The Night Shift | cron `wiki-librarian` (02:30) + `wiki-lint` (02:50) | as-delivered |
| 17 | The Last Rule | blok FACT vs INFERENCE verbatim di 4 SOUL **+ cermin panjang di `WIKI.md` WORKFLOWS**; blok "agen audit pass" yang disuruh tempel ke satu agen ada di `fleet/config/audit-pass.md` (langkah 3c) | as-delivered |
| 18 | Prove It Compounds | `docs/STATUS-UJI.md` (yang sudah dijalankan vs yang harus dibuktikan di Mac) | as-delivered |
| 19 | Hand the Build to Claude Code | tidak perlu — build-nya sudah berupa kode di folder ini | **skipped**: ini instruksi alternatif, bukan fitur |
| 20 | The Dashboard — Door and Contract | `memory/dashboard/server.py` (`/api/data`, `/api/memory/page`, contract drop) | as-delivered |
| 21 | Serve It and Take Inventory | `GET /` melayani `wiki-page.html`; inventaris di `_wiki-health.md` | as-delivered |
| 22 | Wire It to Real Data | `memory/dashboard/wire.py` (8 langkah; demo dihapus saat wiring) | as-delivered |
| 23 | The Web Drop Door, the Lint Button, the Token | `/api/drop`, `/api/memory/lint-now`, cookie `SameSite=Strict` + `X-Wiki-Token` | adapted: token juga lewat cookie agar tombol di halaman jalan |
| 24 | Reach the Dashboard: Tailscale | Host allowlist `MIRAI_WIKI_HOSTS` + bind 127.0.0.1 | as-delivered (langkah Tailscale di sisi Anda) |
| 25 | Git, Last: the Safety Net | commit **di dalam tiap verb** (`<agent>: <page>`, identitas repo-lokal) + verb `snapshot` + job 02:20/03:10 + `wiki-verbs.sh` (11 commit, 0 berkas menggantung) + bagian "Git — the safety net" di WIKI.md | as-delivered |
| 26 | Off-Machine Backup | `offsite-setup.sh` + `offsite-push.sh` (conf 0600, snapshot dulu, `GIT_ASKPASS`, heartbeat, exit 0/3/4/5) + cron 03:40; **dibuktikan** ke repo `/tmp/offtest/offsite.git` | as-delivered |

## Pack tips Hermes (11)

| # | Tip | Artifact | Status |
| --- | --- | --- | --- |
| 1 | Create one more agent | `create-fleet.sh` (pola satu profil) + `workforce.py` deploy | as-delivered |
| 2 | Create several agents at once | `create-fleet.sh` (loop 3 spesialis) | as-delivered |
| 3 | Give every agent its own memory | profil persisten + `wiki` di PATH tiap profil | as-delivered |
| 4 | Brief your agent and build the channels | `operating-rules.md` + `telegram-routing.md` | as-delivered |
| 5 | Isolate the specialists | `create-fleet.sh` menghapus `TELEGRAM_*`/token platform dari `.env` | as-delivered |
| 6 | Create the routing plugin and switch it on | `fleet/plugins/telegram_topic_profiles/` + `plugin.yaml` | as-delivered |
| 7 | Start each topic fresh | prosedur `/new` + tes identitas di routing page | as-delivered |
| 8 | Test every channel | audit 4 poin + tes per topik | as-delivered |
| 9 | If a topic answers as your main agent | tabel troubleshooting di routing page | as-delivered |
| 10 | Make every new scheduled job stay quiet | aturan `[SILENT]` di `cron-jobs.json` + `operating-rules.md` | as-delivered |
| 11 | Make the jobs you already have stay quiet | langkah "cron edit --prompt" (tanpa mengubah jadwal) | as-delivered |

## Yang sengaja tidak dikerjakan (dan kenapa)

1. **Halaman dashboard jadi** — aset unduhan produk, bukan kode.
2. **Upgrade `niu-mission-control`** — keputusan Anda: bikin baru sesuai spec.
3. **systemd, `ss`, `/proc`, `apt`, `loginctl`, `setsid`** — Linux-only.
4. **Yang butuh akun/id asli Anda** — login Composio (mail), thread id Telegram,
   chat id grup, URL repo offsite, domain Tailscale, kunci ElevenLabs. Semua
   tempatnya sudah ada sebagai langkah + perintah + bukti (mail: langkah 3b;
   Telegram: langkah 9; voice: langkah 10), yang tersisa hanya akunnya.
5. **`[SILENT]` pada job yang memang harus selalu mengirim** — tidak dibungkam.
