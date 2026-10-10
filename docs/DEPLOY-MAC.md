# Deploy di Mac — berurutan, tiap langkah ada buktinya

Untuk ekosistem Niumination yang **sudah hidup** (gateway, 10 topik, 9router, A2A):
baca `docs/ADOPT-MAC.md` dulu. Dokumen ini teknis; beberapa langkahnya
(**create-fleet, install-habits, mail-sweep, offsite, plugin Telegram**)
**dilarang** pada adopsi itu.

Kerjakan dari atas ke bawah. Tiap langkah diakhiri perintah yang keluarannya
adalah bukti; kalau bukti tidak muncul, betulkan langkah itu dulu. Tidak ada yang
bind ke 0.0.0.0, tidak ada yang mengeluarkan uang.

Asumsi: macOS, ada `python3` (ada di semua Mac dengan command line tools), dan
Hermes sudah terpasang serta menjawab. Kalau `hermes --version` tidak menjawab,
selesaikan itu dulu.

---

## Langkah 0 — taruh folder ini di tempat yang bukan folder unduhan

```bash
mkdir -p ~/mirai-src && cp -R <folder ini>/* ~/mirai-src/
cd ~/mirai-src && ls
```

Harus terlihat: `memory  fleet  mission-control  docs  README.md`.

## Langkah 1 — kerangka wiki

```bash
mkdir -p ~/wiki
cp -R ~/mirai-src/memory/wiki-skeleton/* ~/wiki/
find ~/wiki -maxdepth 2 | sort
```

**Bukti:** `index.md`, `log.md`, `WIKI.md` ada. Buat folder yang belum ada:
`processed/{personal,business,research,concepts}` dan
`raw/{_inbox,_working,_done,_failed}`.

```bash
cd ~/wiki && git init -q && git add -A && git commit -qm "wiki: halaman pertama" && git log --oneline
```

## Langkah 2 — perintah `wiki` di PATH, untuk SEMUA agen

```bash
mkdir -p ~/.local/bin
install -m 755 ~/mirai-src/memory/skill/wiki/wiki.sh ~/.local/bin/wiki
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.zshrc && source ~/.zshrc
```

**Bukti (jalankan, jangan diasumsikan):**

```bash
cd ~ && wiki index
```

Kalau `command not found`, baris PATH tidak masuk ke shell yang dipakai agen.
Jangan lanjut: semua langkah berikutnya memanggil `wiki`.

Lalu skill-nya ke setiap profil:

```bash
for d in ~/.hermes/profiles/*/ ~/.hermes/; do
  [ -d "$d" ] || continue
  mkdir -p "$d/skills/wiki"
  cp ~/mirai-src/memory/skill/wiki/SKILL.md "$d/skills/wiki/SKILL.md"
done
ls ~/.hermes/profiles/*/skills/wiki/SKILL.md
```

Satu profil terlewat = satu agen terputus dari wiki.

## Langkah 3 — pipeline raw + filing pertama

```bash
mkdir -p ~/wiki/raw/{_inbox,_working,_done,_failed}
wiki rules | head -20
```

**Bukti, sekaligus latihan nyata pertama untuk fleet:**

```bash
wiki file personal <nama-kamu> --agent executor --summary "Pemilik mesin ini" <<'EOF'
# <Nama kamu>

Pemilik. Banda Aceh.
EOF
wiki index && wiki read <nama-kamu> | head -12
```

Kalau perintahnya menolak, baca pesannya — di situ tertulis yang harus dibetulkan.
Jangan bikin file-nya manual untuk menembus penolakan.

## Langkah 3b - mail (opsional, butuh akunmu)

Lewati langkah ini kalau kamu tidak ingin agen membaca mailbox. Kalau ikut, ini
satu-satunya langkah yang perlu login akunmu, jadi dikerjakan tangan.

```bash
curl -fsSL https://composio.dev/install | sh
composio login                     # buka link-nya, setujui di browser
# lalu sambungkan mailbox ke agen mail-nya, dan ke agen itu saja:
composio connect gmail --profile research
```

Blok `## MAIL SWEEP` sudah ada di `fleet/profiles/RESEARCH-SOUL.md` (verbatim dari
paket). Kalau kamu menyambungkan mailbox ke profil lain, **pindahkan blok itu** ke
SOUL profil itu: job `wiki-mail-sweep` menjalankan operasi yang harus ada di SOUL
yang dipakai.

**Bukti:** minta agen itu membacakan subjek tiga mail terbaru. Kalau dia tidak
bisa, mail-nya belum tersambung dan job `wiki-mail-sweep` belum boleh dinyalakan
(bulan pertama: cukup lihat `_mail-seen.md` mulai terisi).

## Langkah 3c - audit pass (satu agen saja)

Sesudah sekian lama dipakai, halaman lama perlu dilabeli: kalimat yang berupa
kesimpulan diberi `(inference, <profil>, tanggal)`. Bloknya, cara memilih agennya,
dan cara membuktikannya ada di `fleet/config/audit-pass.md`. Jangan pasang ke semua
profil: paketnya memang menyuruh satu agen yang paling banyak mengisi halaman.

## Langkah 3d - git: jaring pengaman (5 menit, jangan ditunda)

Selama ini wiki belum punya riwayat: satu halaman yang tertimpa hilang untuk selamanya.
Sejarah baru dimulai **hari ini**, jadi langkah ini justru yang pertama-tama.

```bash
cd ~/wiki
cp ~/mirai-src/memory/wiki-skeleton/.gitignore .   # mesin: lock + isi raw/_*_ (folder tetap)
git init -q
git config user.name  MIRAI            # repo-lokal, SENGAJA bukan --global:
git config user.email mirai@localhost  # identitas repo lain milikmu tidak disentuh
git add -A && git commit -qm "the wiki as it stands today"
```

**Bukti 1:** `git -C ~/wiki log --oneline | head -3` menampilkan commit itu.

**Bukti 2 (yang sesungguhnya):** satu tulisan lewat verb menghasilkan satu commit
dengan pesannya sendiri.

```bash
wiki file personal <nama-kamu> --agent executor --summary "Pemilik mesin ini" <<'EOF'
# <Nama kamu>

Pemilik. Banda Aceh.
EOF
git -C ~/wiki log -1 --pretty='%h %s'     # expect: <sha> executor: <nama-kamu>
```

Mulai sekarang setiap verb menulis **dan** meng-commit di dalam lock yang sama. Malam
nanti dua job snapshot menjaganya:

| Job | Jam | Yang dijalankan |
| --- | --- | --- |
| `wiki-opening-snapshot` | 02:20 | `wiki snapshot --label 'opening snapshot'` - menyapu berkas yang tak lewat verb (lampiran, suntingan mesin). Malam bersih = `nothing to snapshot`, dan itu sukses. |
| `wiki-closing-snapshot` | 03:10 | `wiki snapshot --allow-empty --label 'closing snapshot'` - penanda hari, apa pun yang terjadi. |

Keduanya lewat lock yang sama: kalau ada penulis lain, `wiki is busy, nothing was
snapshotted` (exit 3) dan **tidak ada** yang ter-commit diam-diam.

**Bukti 3 - pemulihan, dijalankan sekali di depan mata** (dua perintah yang akan
menyelamatkanmu suatu hari):

```bash
git -C ~/wiki log --oneline --since=midnight -- processed/personal/<nama-kamu>.md
SHA=$(git -C ~/wiki log -1 --format=%h -- processed/personal/<nama-kamu>.md)
git -C ~/wiki show "$SHA":processed/personal/<nama-kamu>.md > ~/wiki/processed/personal/<nama-kamu>.md
wiki snapshot --label "restored <nama-kamu>" && wiki log --agent executor "restored <nama-kamu> from $SHA" --pages <nama-kamu>
```

`git show <sha>:<path>` mencetak berkas apa adanya tanpa menyentuh yang lain - itulah
seluruh triknya. Seluruh rangkaian ini diuji ulang oleh
`bash ~/mirai-src/memory/skill/wiki/tests/wiki-verbs.sh` (25 pemeriksaan, termasuk
pemulihan itu, tanpa menyentuh wiki sungguhan).

## Langkah 3e - jaring kedua: simpan juga di luar Mac (opsional, 10 menit)

Git di Mac ini melindungi dari salah ketik dan salah timpa. Ia **tidak** melindungi dari
Mac yang hilang, SSD yang mati, atau kopi yang tumpah. Untuk itu: satu repo **privat** di
luar (GitHub/GitLab/apa pun - intinya bukan mesin ini) yang menerima dorongan tiap malam.

```bash
# 1. buat repo kosong PRIVAT di luar; jangan tambahkan README di sana
# 2. jalankan, dan tempelkan URL-nya saat diminta (token TIDAK akan muncul di layar):
bash ~/mirai-src/memory/schedule/offsite-setup.sh
```

Skrip itu: menulis kata sandi/token ke `~/.config/mirai/wiki-offsite.conf` dengan mode
**0600**, membuat helper `GIT_ASKPASS` 0700, lalu mencoba `git ls-remote` sekali sebagai
bukti kredensialnya benar - dan **berhenti dengan jelas** kalau salah, bukan diam-diam
gagal nanti malam.

Malamnya jam 03:40 `wiki-offsite` menjalankan `offsite-push.sh`, yang:

1. **snapshot dulu** - tidak ada satu pun perubahan menggantung yang ikut terkirim;
2. mendorong satu cabang saja (`HEAD`, tidak semua);
3. menulis heartbeat ke `~/wiki/_wiki-health.md`, sukses **atau** gagal;
4. membaca kembali log-nya dan berteriak kalau token/kata sandi sampai tertulis.

**Bukti:**

```bash
DRY=1 bash ~/mirai-src/memory/schedule/offsite-push.sh   # menampilkan rencananya, tidak mendorong
bash ~/mirai-src/memory/schedule/offsite-push.sh          # exit 0 = terkirim
tail -3 ~/wiki/_wiki-health.md
```

Kode keluar yang mungkin: `0` terkirim · `3` wiki sibuk (tidak ada yang dikirim, ulangi
nanti) · `4` belum disetel · `5` push gagal. Angka-angka itu yang kamu cari di log dulu
kalau suatu pagi heartbeat-nya berhenti.

## Langkah 4 — standing orders (cron Hermes)

Definisi lengkapnya di `memory/schedule/cron-jobs.json` (prompt verbatim +
heartbeat). Tentukan dulu **zona waktu scheduler** dengan percobaan:

1. Bikin job sekali jalan 2 menit dari sekarang yang menulis waktu.
2. Catat kapan benar-benar menyala, dan di zona mana.
3. Pasang semua job di zona ITU, bukan zona yang kamu tebak.

| Job | Jadwal | Tugas |
| --- | --- | --- |
| `wiki-dropbox` | `*/30 * * * *` | menguras `raw/_inbox` lewat INGEST |
| `wiki-mail-sweep` | `0 7 * * *` | mail pemilik lewat INGEST |
| `wiki-opening-snapshot` | `20 2 * * *` | `wiki snapshot` sebelum shift malam (lock, exit 3 = sibuk) |
| `wiki-librarian` | `30 2 * * *` | makna: kontradiksi, klaim basi, link |
| `wiki-lint` | `50 2 * * *` | bentuk: rahasia dulu, lalu index/format |
| `wiki-closing-snapshot` | `10 3 * * *` | `wiki snapshot --allow-empty` — penanda hari, tanpa syarat |
| `wiki-offsite` | `40 3 * * *` | opsional: `offsite-push.sh` (snapshot + push; token dibaca saat itu) |

**Bukti:** `hermes cron list` menampilkan ketujuhnya, dan `~/wiki/_wiki-health.md`
bertambah heartbeat tanpa kamu sentuh.

## Langkah 5 — Mission Control

```bash
bash ~/mirai-src/mission-control/scripts/install-mac.sh
```

Skrip: membuat `~/mirai/data`, menyalin `web/dashboard.html` → `~/mirai/dashboard.html`,
menyulihkan `$HOME` ke plist, `launchctl bootout/bootstrap/kickstart`, lalu
**membuktikan `/api/ping` dan `/api/agents` sebelum mengaku sukses**.

**Bukti:**

```bash
lsof -nP -iTCP:8800 -sTCP:LISTEN          # 127.0.0.1, bukan *
curl -s localhost:8800/api/ping
launchctl print gui/$(id -u)/com.mirai.mission-control | head -20
```

Restart nanti: `bash ~/mirai-src/mission-control/scripts/restart.sh` (menampilkan
pid sebelum-sesudah, gagal keras kalau port tidak diambil lagi).
Log: `~/mirai/data/mission-control{,.err}.log`. Backup malam:
`bash ~/mirai-src/mission-control/scripts/backup.sh`.

## Langkah 5b - dari HP, dan hanya kamu (Tailscale + kunci, 15 menit)

Port 8800 hanya menjawab di `127.0.0.1`: aman, tapi kamu tidak bisa membukanya dari HP.
Yang **tidak** boleh dilakukan: membuka 8800 ke internet, `tailscale funnel`, atau
port-forward. Yang boleh: Tailscale (jaringan pribadi, terenkripsi, tanpa port terbuka),
**plus** kunci token, karena jaringan saja tidak pernah cukup untuk panel yang bisa
menjalankan agen.

```bash
# di Mac dan di HP: pasang Tailscale, login akun yang sama
bash ~/mirai-src/mission-control/scripts/tailscale-serve.sh --status   # baca dulu, jangan ubah
bash ~/mirai-src/mission-control/scripts/tailscale-serve.sh            # serve https -> 127.0.0.1:8800
```

Skripnya membaca status dulu lalu memetakan lewat `http://127.0.0.1:8800` supaya server
tetap tidak pernah mendengarkan di alamat publik; ia memeriksa dengan `lsof` bahwa tidak
ada yang terbuka, dan **menolak funnel** sambil menjelaskan alasannya.

Sekarang nama tailnet-mu itu tamu yang tidak dikenal bagi server: ia hanya menjawab
`127.0.0.1`, `localhost`, `::1` dan nama yang kamu daftarkan. Daftarkan namanya di
`~/mirai-src/mission-control/secrets.env`:

```bash
MIRAI_HOSTS=macbook.tailnet-xxxx.ts.net     # nama dari `tailscale serve status`
```

Lalu nyalakan kuncinya. Urutannya penting: **kunci dulu, baru tautan.**

```bash
# 1. kunci: MIRAI_AUTH=on + token 0600 dibuat sendiri kalau belum ada
bash ~/mirai-src/mission-control/scripts/restart.sh
ls -l ~/mirai/data/auth.token          # -rw------- (0600), bukan 644

# 2. tautan sekali-tap untuk HP (token ikut jadi cookie HttpOnly 30 hari):
bash ~/mirai-src/mission-control/scripts/link.sh
```

`link.sh` mencetak `http://127.0.0.1:8800/?k=…` dan, kalau Tailscale hidup, juga
`https://<nama-tailnet>/?k=…`. Token itu **tidak sekali pakai**: tautan lama tetap sah,
jadi simpan satu di HP dan jangan bikin yang baru tiap kali. Yang perlu kamu tahu:

| Keadaan | Yang terjadi |
| --- | --- |
| Buka halaman tanpa token | halaman **sign-in** milik MIRAI (bukan dashboard, bukan 404) |
| API dipanggil tanpa token | `401 {"ok": false, "error": "authentication required"}` - JSON, karena pemanggilnya program |
| Buka `?k=<token>` | halaman terbuka **dan** cookie HttpOnly terpasang; kunjungan berikutnya tanpa tautan |
| Token salah | 401, dan tidak ada petunjuk apa pun |
| `/api/ping` | sengaja **tetap terbuka**: uptime check lokal tidak boleh jadi merah karena gate |
| Host bukan loopback/tailnet | 403, dengan pesan yang menyebut `MIRAI_HOSTS` |
| Token di log | tidak pernah: `?k=` diredaksi jadi `?<redacted>` (ada pemeriksaan otomatisnya) |

**Bukti:** dari HP (Tailscale aktif), buka tautan dari `link.sh` → dashboard tampil; lalu
coba `http://<nama-tailnet>:8800/api/agents` tanpa token di aplikasi lain → `401`.

Merasa belum perlu? Biarkan `MIRAI_AUTH=off` dan jangan jalankan `tailscale-serve.sh`:
gate mati berarti tidak ada yang berubah dari sebelumnya, dan `link.sh` dengan sendirinya
menolak menyalakan yang belum dinyalakan.

## Langkah 6 — halaman dashboard

Konsol MIRAI (15 halaman, tanpa CDN) sudah terpasang sebagai `~/mirai/dashboard.html`
dan langsung jalan.

Kalau kamu punya **halaman dashboard yang jadi** (±9 MB dari produk): simpan sebagai
`~/mirai/dashboard.html` dan reload. Backend ini menjawab semua route yang halaman
itu pakai; kalau ada panel yang bilang "belum ada di build ini", datanya memang
belum ada di mesin ini, bukan backend error.

**Bukti:** halaman terbuka offline (tanpa CDN), dan tab Agents menampilkan
profil nyata dari `~/.hermes`.

## Langkah 7 — dashboard wiki (port 8899, opsional)

```bash
mkdir -p ~/wiki-dashboard && cd ~/wiki-dashboard
cp ~/mirai-src/memory/dashboard/server.py .
cp ~/mirai-src/memory/dashboard/wiki-page.html .   # halaman yang sudah di-wire
python3 server.py 8899
curl -s localhost:8899/api/data | head -c 300
```

Tokennya dibuat di `~/wiki-dashboard/dashboard.token` (0600) dan dikirim ke
browser sebagai cookie `SameSite=Strict` saat halaman dibuka — jadi tombol Lint /
Commit / drop door di halaman itu jalan tanpa ada rahasia tertulis di HTML.

## Langkah 8 — fleet

```bash
bash ~/mirai-src/fleet/scripts/create-fleet.sh --dry-run   # lihat dulu
bash ~/mirai-src/fleet/scripts/create-fleet.sh
bash ~/mirai-src/fleet/scripts/install-habits.sh
```

`create-fleet.sh` meng-clone tiap spesialis, menyalin login + config (tanpa token
platform), menulis SOUL-nya, lalu memverifikasi dengan satu turn nyata.
`install-habits.sh` menambahkan tiga blok verbatim ke setiap SOUL dan mencetak
hitungan per file sebagai bukti.

**Bukti:**

```bash
grep -l "own file tools" ~/.hermes/SOUL.md ~/.hermes/profiles/*/SOUL.md
hermes -p research chat -q "What do you know about me?" -Q --source mirai -c mirai-test --create-if-missing
```

Jawabannya harus mengutip halaman wiki yang kamu file di langkah 3.

## Langkah 9 — topik Telegram

Ikuti `fleet/config/telegram-routing.md` dari atas ke bawah: bot admin dengan
Manage topics, satu topik per agen, blok platform di spesialis dihapus, plugin di
`~/.hermes/plugins/telegram_topic_profiles/` dengan id asli di `topics.json`,
`profile_routes` bila Hermes 0.21+, lalu enable, restart, dan jalankan audit
empat poin + tes `/new` + "who are you" di setiap topik.

## Langkah 10 — voice (opsional)

Mode 1 (dikte browser) dan 2 (Whisper lokal di 127.0.0.1:8768) diatur dari tab
Voice. Tanpa server Whisper lokal, mode 2/3 mengembalikan alasan yang jelas,
bukan menggantung. Tidak ada yang memanggil cloud.

## Langkah 11 — "selesai" itu seperti ini

- `wiki index` menampilkan halamanmu; `wiki log` menunjukkan siapa filing apa, kapan.
- Tujuh cron job terdaftar dan `_wiki-health.md` berdetak sendiri.
- `http://127.0.0.1:8800` menampilkan profil asli dengan status asli.
- Pesan di topik spesialis dijawab oleh spesialis itu.
- Tidak ada yang menjawab di antarmuka selain 127.0.0.1.

## Langkah 12 - bukti di Mac INI (satu perintah)

Semua yang ada di `STATUS-UJI.md` sebagai "harus dibuktikan di Mac" sudah jadi pemeriksaan
di satu berkas - jalankan, jangan percaya catatan:

```bash
bash ~/mirai-src/mission-control/tests/mac-verify.sh          # ~10 detik, tidak mengubah apa pun
bash ~/mirai-src/mission-control/tests/mac-verify.sh --turn   # + satu turn agen sungguhan
```

Yang diperiksa (dan **tidak** ditulis ke `~/.hermes` sedikit pun): plist launchd valid +
KeepAlive, port 8800 hanya di loopback, `/api/ping`, jumlah agen nyata, `/api/health`
membaca macOS (bukan jalur Linux), `hermes profile list` + ketujuh cron job, `wiki` ada di
PATH dan wiki-nya repo git dengan identitas repo-lokal, snapshot terakhir < 36 jam, page
dan `/lib/mediapipe/hand_landmarker.task` terlayani, mode 0600 `auth.token`/`secrets.env`,
dan `--turn` mengirim satu pesan ke agen pertama lalu memeriksa `"ok": true`.

Gagal itu ditampilkan sebagai `FAIL` **beserta perintah perbaikannya**; `SKIP` tidak
dihitung gagal. Keluaran akhirnya satu baris: berapa lulus, berapa gagal.

## Empat masalah yang benar-benar sering terjadi

| Gejala | Sebab | Perbaikan |
| --- | --- | --- |
| `wiki: command not found` di dalam turn agen | shell agen tidak memuat `~/.zshrc` | tambahkan PATH ke environment profil itu, atau install ke `/usr/local/bin` |
| Profil baru tidak menjawab apa pun | `auth.json` tidak tersalin | jalankan ulang `create-fleet.sh`; ia menyalin yang hilang |
| Gateway menolak start setelah tambah profil | masih ada token Telegram di spesialis | hapus blok `platforms:` + baris `TELEGRAM_*` di profil itu |
| Port 8800 terpakai | masih ada salinan lain | `bash mission-control/scripts/restart.sh` (mencari pemilik port) |
