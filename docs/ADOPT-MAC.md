# ADOPT-MAC — Hermes Mac menerapkan paket MIRAI

Baca ini **sebelum** `install-mac.sh`, `create-fleet.sh`, atau `install-habits.sh`.

**Sudah selesai di Mac** (jangan diulang): rapikan 238 skill, arsip niu-mc. Bukti: [`MAC-STATE.md`](MAC-STATE.md).

Alur: pekerjaan selesai di Arena → pemilik download workspace → **Hermes di Mac** yang menerapkan. Arena tidak menulis `~/.hermes` kecuali pemilik sudah izinkan satu suntingan yaml thread 1.

Paket di `mirai/` = kode + wiki + console. Adopsi **bukan** drop-in 3 persona generik.

---

## Keputusan terkunci (2026-10-10)

| | |
| --- | --- |
| Router Telegram | `config.yaml` (10 thread). `profile_routes` **tidak** ditulis. Plugin MIRAI **OFF**. |
| Profile Hermes | Tetap **1** (`default` / Atria-Dawn-Preview). **`create-fleet.sh` dilarang.** 3 SOUL research/writer/developer **tidak** dipasang. |
| Off-limits | `ai.hermes.gateway`, 9router `:20128`, A2A `:9900`, tulis SOUL.md / `install-habits.sh`. **Tulis `config.yaml` dilarang kecuali satu baris:** persona thread **1** = Triage/General (bukan Orkestrator). `profile_routes` tetap tidak ditulis. |
| Skill 238 duplikat | **Selesai di Mac.** 0 duplikat, 13 binding resolve, 804 = `code-audit`. Jangan unset/ulang. |
| Cockpit | Boleh kosong (kanban 0, thread fresh-reset). Jangan seed kartu palsu. |
| niu-mission-control lama | **Sudah diarsipkan** di Mac. Jangan hidupkan `:5200`. |
| Wiki | **Lengkap:** skeleton di `$HOME/Desktop/Niumination/wiki` (bukan `~/wiki`), 9 verb, lock = `mkdir` (macOS tidak punya `flock`), skill wiki ke profile **default saja**, dashboard `:8899`, cron malam **tanpa** 07:00 dan 03:40. |
| Mail-sweep / offsite | Skrip **ada** di paket. **Jangan** `hermes cron create` untuk `wiki-mail-sweep` dan `wiki-offsite`. |
| Python LaunchAgent | `/usr/bin/python3` (3.9.6), bukan 3.14.8 di PATH shell. |
| Port | `:8800` Mission Control, `:8899` wiki dashboard. Jangan `:9900` / `:20128`. |

Detail fungsi 10 topik: [`TOPIK-NIUMINATION.md`](TOPIK-NIUMINATION.md). Deploy teknis berurutan (bukti per langkah): [`DEPLOY-MAC.md`](DEPLOY-MAC.md) — **filter dengan larangan di bawah**, jangan ikut langkah fleet/habits/mail/offsite.

---

## Dilarang (gagal adopsi = menjalankan ini)

```text
create-fleet.sh
install-habits.sh
hermes profile create …
menulis ~/.hermes/config.yaml
menulis profile_routes
mengubah launchd ai.hermes.* / com.niumination.*
menghidupkan niu-mission-control atau MATA
hermes cron create wiki-mail-sweep
hermes cron create wiki-offsite
menyalin 3 SOUL generik ke ~/.hermes/profiles/
```

`install-mac.sh` hanya boleh `launchctl` untuk **`com.mirai.mission-control`** (dan wiki dashboard jika dipasang). Tidak `kickstart` gateway.

Skill wiki: salin `SKILL.md` ke `~/.hermes/skills/wiki/` (profile default). **Jangan** loop ke `~/.hermes/profiles/*/ ` — folder itu **kosong** dan harus tetap kosong.

---

## Yang dikerjakan, berurutan

Bukti = output perintah, bukan “sudah”.

### A. Letakkan sumber

```bash
# workspace hasil download → bukan folder Downloads yang hidup
mkdir -p ~/mirai-src && cp -R <isi-workspace>/mirai/. ~/mirai-src/
cd ~/mirai-src && ls
# harus: memory  fleet  mission-control  docs  README.md  lib
```

### B. Wiki lengkap (tanpa habits ke SOUL)

Ikuti DEPLOY-MAC Langkah 1–3 + 3d (`wiki` di PATH, `wiki index` dari `~`, git init `~/wiki`, skeleton, `wiki file` latihan dengan `--agent default` **bukan** executor-generik).

Dashboard wiki: DEPLOY-MAC bagian server memory (`:8899`). LaunchAgent sendiri, label `com.mirai.wiki-dashboard` atau sesuai skrip yang ada — **bukan** nama niu.

### C. Cron wiki — 5 job, bukan 7

`hermes cron list` dulu. Jangan duplikat nama.

| Pasang | Nama | Jadwal |
| --- | --- | --- |
| ya | wiki-opening-snapshot | 02:20 |
| ya | wiki-librarian | 02:30 |
| ya | wiki-lint | 02:50 |
| ya | wiki-closing-snapshot | 03:10 |
| ya | wiki-dropbox | */30 |
| **tidak** | wiki-mail-sweep | 07:00 |
| **tidak** | wiki-offsite | 03:40 |

Prompt job: `memory/schedule/cron-jobs.json`. Ganti `<default profile>` / `<best reader>` = **profile `default`** (satu-satunya yang ada). Jangan ciptakan profile librarian.

`wiki-lint.heartbeat_list` di json masih menyebut mail-sweep + offsite — itu normal; job yang tidak dipasang tidak akan punya heartbeat, lint boleh laporkan “missing” sampai kamu putuskan pasang.

### D. Mission Control `:8800`

`mission-control/scripts/install-mac.sh` dari `~/mirai-src`. Salin `lib/mediapipe` jika ada di paket.

**Jangan** `link.sh` / gate token ke internet / Tailscale sampai pemilik minta. Lokal `127.0.0.1:8800` cukup.

`tests/mac-verify.sh` akan **gagal** pada cek “3 profile / fleet” — itu **bukan** regresi. Yang harus hijau: ping, listen `127.0.0.1` saja, plist, wiki git + `wiki snapshot`, cron 5 nama di atas (bukan 7). Catat FAIL yang disengaja.

### E. Telegram / topics.json

Sudah terisi id+label di paket. **Jangan** nyalakan plugin. Verifikasi manual: pesan di topik 802 tidak perlu MIRAI untuk sampai ke persona yaml.

Usulan fungsi **disetujui** pemilik (lihat TOPIK-NIUMINATION.md). 7402 = sandbox. Setelah cockpit hidup, Hermes Mac **boleh** satu suntingan yaml: thread 1 persona → Triage/General. Jangan sentuh 9 thread lain, jangan `profile_routes`.

### F. Tidak dikerjakan di adopsi ini

- Roster cockpit dari yaml (kode masih generik). UI kosong = jujur.
- Composio Gmail, remote git offsite, ElevenLabs, kamera.
- Rapikan 238 skill.

---

## Checklist pemilik sebelum bilang “MIRAI hidup”

- [ ] `lsof` `:8800` → `127.0.0.1` saja  
- [ ] `curl -sf http://127.0.0.1:8800/api/ping`  
- [ ] `wiki index` dari `$HOME`  
- [ ] `~/wiki` git log ada commit kerangka  
- [ ] `hermes cron list` memuat 5 nama wiki, **tanpa** mail-sweep/offsite baru  
- [ ] `launchctl print` gateway Hermes **tetap** PID-nya, bukan restart karena MIRAI  
- [ ] `~/.hermes/profiles/` masih tidak ada  
- [ ] `config.yaml` diff **hanya** persona thread 1 (Orkestrator → Triage/General), atau belum diubah sama sekali — bukan 9 thread lain  
- [ ] tidak ada LaunchAgent `com.niumination.missioncontrol` yang dihidupkan  

---

## Kalau ragu

Berhenti. Jangan “sekalian create-fleet”. Tulis apa yang gagal, kirim ke Arena atau sesi Hermes berikutnya. Paket ini aman didiamkan di `~/mirai-src` tanpa LaunchAgent.
