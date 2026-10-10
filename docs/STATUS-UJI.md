# Status uji — apa yang sudah dijalankan, apa yang harus dibuktikan di Mac

Jujur soal batas: build ini disusun dan diuji di sandbox Linux (Python 3.13),
sedangkan targetnya Mac. Semua kode stdlib-only dan aman untuk Python 3.9+, tapi
perintah khas macOS (`vm_stat`, `sysctl`, `lsof`, `launchctl`) tidak bisa
dijalankan di sini — itu yang ada di daftar "harus dibuktikan di Mac".

## Sudah dijalankan di sini, dan hasilnya

| Yang diuji | Perintah | Hasil |
| --- | --- | --- |
| Semua 54 route backend | `bash mission-control/tests/prove.sh` | 17 GET membalas `ok:true`; siklus hidup misi NX-1001 penuh; terminal SSE mengeluarkan `MIRAI_OK`; **0 traceback** |
| Semua penolakan | idem | bad action, `../../etc/passwd`, `..` di path, konfirmasi salah, runtime salah, verb cron salah, body bukan JSON, body array JSON, 30 karakter display_name, `operator_name`, kunci tak dikenal — semuanya JSON `ok:false` dengan pesan yang menyebut masalahnya |
| Batas 30 MB | idem | body asli 32 MB → **413 dalam ~1 ms**, tanpa membaca body |
| Halaman + /lib | idem | `GET /` 200 (byte sama dengan file di disk), gzip lebih kecil, `If-None-Match` → 304, `/index.html` sama, `/lib/mediapipe/*.mjs|.task` tipe MIME benar, traversal `..` → 404 |
| Gate token (prompt 43) | `bash mission-control/tests/prove.sh` (blok gate, port 8803) | halaman tanpa token → halaman sign-in 200 (bukan dashboard, bukan 404); API tanpa token → JSON 401; token benar lewat `X-Auth-Token` **dan** `Bearer` → 200; tautan `?k=` memasang 1 cookie dan **cookie itu sendiri membuka halaman + API**; token salah → 401; `/api/ping` 200; token 0600; **tidak ada token di log** |
| Host allowlist (prompt 42) | idem (blok host, port 8802/8804) | `Host: evil.example` → 403 dengan pesan yang menyebut `MIRAI_HOSTS`; nama tailnet (di `MIRAI_HOSTS`) → 200; `evil` di instance itu tetap 403; 0 traceback |
| Penulisan ke `~/.hermes` | idem + inspeksi | hanya dua jalur yang menulis: cron store (CLI) dan file editable (dengan backup). Sisa `roster.py`/`traffic.py` mode baca |
| `wiki.sh` 9 verb | `bash memory/skill/wiki/tests/wiki-verbs.sh` | 7 grup, **semua cocok**: commit per-verb (11 commit, 0 berkas menggantung), `snapshot` (bersih = `nothing to snapshot`, `--allow-empty` = penanda hari, lock dipegang → exit 3), `was_filed` lewat `git log --all`, pemulihan hidup dari commit pertama sebuah halaman, dan penolakan lainnya (halaman berubah, nama dobel, charset salah, raw slug dobel, log halaman belum ada, hapus `raw/`) |
| Dashboard wiki | `bash memory/dashboard/tests/wiki-e2e.sh` | 9 blok, semua cocok: halaman 264.895 B byte-sama dengan file (satu berkas, tanpa CDN), cookie `HttpOnly; SameSite=Strict`, `/api/data` (stats/nodes/links/lint dari `_wiki-health.md`), `/api/memory/page` (tembus path ditolak 400, halaman hilang 404, berkas meta), tulis tanpa token ditolak, drop door (file, link, bukan data: URL, nama jahat, tabrakan → `note-2.txt`, jendela 5 detik), `lint-now` + rate limit, `commit` **lewat verb `wiki snapshot`** dengan identitas MIRAI sendiri, lock dipegang → **409 `wiki is busy`**, 405 + `Allow`, 404, Host asing 403, klien yang menggantung tidak meninggalkan traceback, halaman fallback + `/upload`, **0 traceback** |
| Halaman wiki yang di-wire | `python3 memory/dashboard/wire.py` | 8 langkah wiring kena semua; demo lama dihapus di langkah yang sama |
| Smoke dari nol | `bash mission-control/tests/smoke.sh` | `tests/fixture.sh` membangun ~/.hermes percobaan (2 profil + cron store + `roles.json` 14 role) tiap kali; /api/agents 2 agen, penolakan settings (5), cache 600 s terbukti (force=1 melewatinya). Port tetap 8801, dan pindah sendiri kalau benar-benar terpakai |
| `restart.sh` tanpa LaunchAgent | `HOME` percobaan, port 8896 | run 1: owner `none` → pid baru + `/api/ping` menjawab; run 2: pid lama (2953) ditukar ke 2975. Jalur `setsid` dijaga `command -v` (macOS tidak punya setsid) |
| Konsol MIRAI (dashboard.html) | dijalankan di Node dengan DOM/network palsu | **15 halaman, 0 error render**; semua panggilan `fetch` di halaman cocok dengan route yang terdaftar; tak ada kelas CSS yang dipakai tanpa aturan |
| Pratinjau tampilan konsol | `mission-control/web/ui-preview.html` dibuka di browser (tanpa server) | 15 halaman hasil render asli dengan data contoh: bisa dilihat langsung sebelum MIRAI dipasang; satu berkas, tanpa CDN |
| Plist launchd | `plistlib.load` | parse bersih, `KeepAlive`+`RunAtLoad` true, PATH memuat `~/.local/bin` + Homebrew |
| 17 modul server | `python3 -m py_compile` | semua compile |
| 8 skrip shell | `bash -n` | semua lolos |

## Harus dibuktikan di Mac (langkahnya sudah ada di DEPLOY-MAC.md)

Tabel ini sudah menjadi perintah: `bash mission-control/tests/mac-verify.sh` menjalankan
pemeriksaan yang bisa diotomatiskan (`--turn` menambah satu turn agen sungguhan) dan
mencetak FAIL beserta perintah perbaikannya. Sisanya yang benar-benar butuh tangan
(kamera, bot Telegram, server Whisper) tetap di bawah ini.

| Hal | Kenapa belum | Cara membuktikan |
| --- | --- | --- |
| `launchctl bootstrap` + KeepAlive | launchd tidak ada di Linux | langkah 5: `launchctl print gui/$(id -u)/com.mirai.mission-control` |
| Pembacaan health macOS (`vm_stat`, `sysctl`, `ps`) | hanya Linux di sini | tab Health: CPU, memori, disk, volume, proses harus masuk akal (jalur Linux tetap ada untuk container) |
| Turn nyata ke Hermes | CLI Hermes tidak ada di sandbox | langkah 5/8: `POST /api/chat` → balasan nyata; `curl /api/models` menampilkan provider asli |
| Mode board misi (`hermes kanban`) | butuh Hermes | `POST /api/missions` lalu approve; kartu muncul di papan |
| `workforce deploy` (clone profil) | butuh Hermes + login | tab Deploy: satu agen baru, probe terakhir harus mengembalikan kalimat |
| MediaPipe Hand mode | modelnya sudah diunduh + sha256-nya diperiksa di sini (`lib/mediapipe/SHA256SUMS.txt`) | sudah: `/lib/mediapipe/hand_landmarker.task` → 200. Yang tinggal di Mac: tab Hand mode + izin kamera |
| Routing topik Telegram | butuh bot + grup nyata | `fleet/config/telegram-routing.md` langkah 6 |
| Voice mode 2/3 | butuh server Whisper lokal | tab Voice: mode 2/3 harus menyebut engine-nya, bukan diam |
| Snapshot git di vault asli | repo percobaan sudah diuji | tombol Commit di dashboard wiki → `git -C ~/wiki log --oneline` |

## Bug yang ditemukan justru karena diuji

1. **Plist tidak valid XML** — komentar berisi `systemd --user`, dan `--` ilegal di
   dalam komentar XML. `launchctl bootstrap` akan menolaknya. Sudah diperbaiki dan
   di-parse ulang.
2. **Rate limiter drop door** menghitung percobaan yang gagal, jadi drop yang sah
   di detik berikutnya ikut ditolak. Sekarang hanya drop yang benar-benar mendarat
   yang mencap waktu.
3. **Jalur tulis dashboard wiki** pernah kehilangan penangan request-nya saat
   halaman fallback di-restyle; ditemukan dan ditulis ulang, lalu dibuktikan sama
   perilakunya lewat `wiki-e2e.sh` (itulah kenapa skrip ini ada di paket, bukan di
   komputer saya).
4. **Gate yang tidak mengunci halamannya sendiri.** Urutan di `_dispatch` menaruh
   penyajian halaman/`/lib` **sebelum** gate, jadi halaman dashboard tetap terbuka
   tanpa token - dan cookie `?k=` tidak pernah terpasang di halaman itu. Sekarang gate
   berjalan lebih dulu, dan header gate (termasuk `Set-Cookie`) ikut di halaman 200/304.
   Terbukti di `prove.sh`: `cookie alone → 200 200`.
5. **Semua `<script>` di halaman wiki tidak pernah jalan.** Tipe MIME sisa Cloudflare
   (`36bf…-text/javascript`) membuat browser memperlakukannya sebagai data block.
   Sesudah dibuang, satu error sintaks yang tersembunyi ikut ketahuan (string satu
   kutip yang berisi baris baru). Bukti: `node --check` bersih + jsdom menjalankan
   halaman (23 ikon jadi `<svg>`, 0 error).
6. **`fetch-mediapipe.sh` salah ukuran minimum** — `vision_bundle.mjs` yang asli
   152 KB ditolak sebagai "short download" karena batasnya ditulis 1 MB. Ketahuan
   justru saat skripnya dijalankan sungguhan. Sekarang batasnya sesuai berkas aslinya,
   dan ada pemeriksaan sha256.

## Cara menjalankan ulang semua ini

```bash
bash mission-control/tests/prove.sh              # backend penuh (~80 detik, port 8802, HOME sementara)
bash mission-control/tests/smoke.sh              # versi cepat dari nol (port 8801; fixture.sh bikin ~/.hermes percobaan)
bash memory/dashboard/tests/wiki-e2e.sh          # dashboard wiki end-to-end (~35 detik, port 8903/8904)
bash memory/skill/wiki/tests/wiki-verbs.sh       # 9 verb + git + snapshot (~20 detik, wiki percobaan)
bash mission-control/tests/mac-verify.sh         # DI Mac yang sebenarnya: launchd, lsof, hermes, wiki, gate
python3 memory/dashboard/wire.py "<template>"    # ulang wiring halaman wiki
```

Semuanya memakai HOME sementara dan port sendiri, jadi aman dijalankan di Mac
yang sudah terpasang MIRAI. `tests/fixture.sh` menolak jalan kalau `HOME`/
`MIRAI_DIR` tidak di bawah `/tmp` — pencegah paling murah untuk "uji" yang
menimpa crew sungguhan. `wiki-e2e.sh` menyentuh `~/wiki` lewat `CREW_WIKI_DIR`
(`/tmp/wiki-e2e`) dan mengembalikan `dashboard.token` / `lint-request.txt` ke
keadaan semula setelah selesai.
