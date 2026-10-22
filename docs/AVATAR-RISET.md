# Riset avatar MIRAI — donghua + gerak ringan

Riset sebelum generate. PNG 10 kursi **belum** disentuh. Putaran lama (foto, clipart, robot chrome) tetap ditolak. **Tema utama sekarang: donghua** (instruksi pemilik 2026-10-16), bukan “hindari donghua” dari putaran sebelumnya.

Sumber format: [1](https://www.kalex.studio/blog/lottie-vs-gif-vs-mp4-vs-webm-web-animation-formats) [2](https://ziggle.art/transparent-animated-mascot) [4](https://lottiefiles.com/blog/working-with-lottie-animations/lottie-vs-gif). Bahasa visual: [2](https://medium.com/@kevjay/why-everyone-is-still-sleeping-on-chinese-animation-86fee59b3624) [4](http://demiguo.net/donghua) [5](https://www.polygon.com/entertainment/23421285/donghua-chinese-animation-vs-anime/). Pixel: [3](https://www.sprite-ai.art/blog/2d-pixel-art-style-guide).

---

## 1. Batas jendela MIRAI

- Dashboard **tanpa CDN / tanpa JS library baru**. Lottie & Live2D **gugur** (butuh runtime).
- `avatars.py` sudah sniff PNG / JPEG / **WebP**. GIF belum di `MAGIC`.
- Kartu mosaik kecil: gerak harus **idle 1–3 detik**, loop, tidak ramai 10 kursi sekaligus.
- Target berat: **jauh di bawah 19 MB** sepuluh PNG sekarang. Ambisi: ≤150 KB per kursi, total ≤1,5 MB.

---

## 2. Format (ringan → berat)

| Format | α | `<img>` native | JS | Warna | Ukuran tipikal 3s | Untuk MIRAI |
|--------|---|----------------|----|-------|-------------------|-------------|
| CSS / SVG idle | ya | — | tidak | penuh | <5 KB | rambut, kilau mata, ember di tepi |
| Lottie | ya | tidak | **ya** | vektor | 5–50 KB | **tolak** (CDN/lib) |
| Animated **WebP** | ya | ya | tidak | penuh | 50–300 KB | **kandidat utama** |
| APNG | ya | ya | tidak | penuh | 200 KB–2 MB | cadangan Safari tua |
| GIF | 1-bit | ya | tidak | 256 | 0,5–5 MB | **jangan** — banding, tepi bergerigi di ink |
| WebM α | ya | `<video>` | tidak | penuh | 50–300 KB | 10 `<video>` di mosaik = CPU |
| Pixel spritesheet + CSS | ya | ya | tidak | palet | 20–80 KB | kuat jika pilih pixel-donghua |

**Rekomendasi teknis:** idle **animated WebP** di `<img>` (sama seperti PNG sekarang). Poster statis `.png` 1 frame untuk `prefers-reduced-motion`. Jangan GIF.

---

## 3. Empat konsep visual (pilih satu)

Semua **bust** (kepala–dada), pakaian, latar ink MIRAI, bukan full-body kota.

### A — Donghua 2D idle (disarankan)
Wajah donghua modern: mata tidak “anime jumbo”, tulang pipi lebih ramping, jubah / hanfu / tangzhuang gelap, cel-shade 3 nada, kilau tinta. Gerak: napas 2 px, kedip 8 frame, 1 aksesoris (pita, kertas, lampu). Satu loop 1,5–2 s, 8–12 fps, kanvas 512² → WebP.

Ciri donghua yang dipakai: jubah mengalir, palet peran (bukan rainbow), sapuan seperti *Fog Hill* / ink-wash **tipis** di latar — bukan 3D Nezha CGI.

### B — Pixel-donghua (16-bit)
32×32 atau 64×64, scale `image-rendering: pixelated` di CSS. Palet **satu** 24 warna untuk 10 kursi. Chibi 2–3 kepala. Loop 4–6 frame. Paling ringan, paling “ikon”. Risiko: terasa game, kurang “jendela”.

### C — Chibi donghua diam + CSS
PNG statis chibi; CSS `translateY` 3 px + kedip sprite 2 frame. Nol file animasi. Paling aman a11y.

### D — Ink-wash still
Satu frame sapuan tinta, tanpa loop. Bukan permintaan “seperti gif”, hanya jika gerak ditolak.

**Usul default: A**, dengan C sebagai fallback `prefers-reduced-motion`.

---

## 4. Bible gaya (kalau A)

- Kanvas: 512×512, bust, kamera ¾, mata ke lensa.
- Latar: `oklch` ink, **tanpa** kota neon, tanpa logo.
- Garis: 2 px gelap, fill cel 3 nada, highlight bara tipis di satu sisi.
- Rambut: panjang / ikat sesuai peran, tidak meledak particle.
- Pakaian **wajib** (jubah, mantel, tangzhuang). Bukan armor chrome telanjang.
- Dilarang: foto, clipart stiker, teks di gambar, senjata api modern, watermark.

Gerak **hanya**: kedip, napas, 1 prop. Bukan lari, bukan slash.

---

## 5. Variasi per tupoksi (10 kursi)

Kode file tetap `tr.png` / `tr.webp` agar `pack_for` tidak pecah.

| Kode | Kursi | Archetype donghua | Palet aksen | Prop idle | Nada |
|------|--------|-------------------|-------------|-----------|------|
| **TR** | Inbox #1 | Penjaga gerbang / receptionist sect | krim pudar | lentera kertas bergoyang | ramah, netral |
| **OR** | Orkestrator #13902 | Sect leader / 掌门 | bara + emas tua | jubah sedikit tertiup, stempel | tenang berwibawa |
| **RS** | Research #802 | Cendekiawan / 书生 | biru tinta | gulungan terbuka, debu kertas | fokus |
| **BD** | Builder #803 | Pandai besi / artisan | tembaga | percikan kecil di bahu | kerja |
| **QA** | QA #804 | Hakim / 御史 | putih tulang + ink | kacamata / stempel merah | tajam |
| **KR** | Kreator #1172 | Pelukis / 画师 | merah lacquer | kuas, sehelai pita | ekspresif |
| **SB** | Serbaguna #7402 | Disciple serba-guna / 杂役 | abu hangat | kantung alat bergoyang | ringan |
| **AS** | ASN #8853 | Pejabat sipil / 文官 | hijau gelap dinas | folder / stempel resmi | rapi |
| **CR** | Cron #12595 | Penjaga waktu / 司更 | tembaga jam | pendulum / manik | mekanis halus |
| **ED** | Edu #12707 | Guru / 夫子 | kuning kertas tua | papan / kitab | hangat |

Bukan 10 wajah klon beda topi: **siluet rambut + prop + aksen** harus kebaca di mosaik 160 px.

---

## 6. Pipeline generate (nanti, belum sekarang)

1. Satu still 512² per kode (pilih opsi).
2. Turunan gerak: 8 frame kedip+napas **atau** CSS saja.
3. Encode WebP loop, quality ~70, target ≤120 KB.
4. Still PNG ≤80 KB untuk reduced-motion.
5. `pack_for` boleh `webp` dulu, fallback png.
6. `alt` sudah nama kursi.

Arena image gen = **still**. Frame animasi = turunannya, bukan 10 GIF raksasa.

---

## 7. Keputusan (2026-10-16)

Pemilik: **A + animated WebP**.

Still donghua ada di `mission-control/web/avatars/_new/` (PNG mentah ~1,8 MB/file; **WebP still** 19–36 KB, total **~280 KB**). Paket produksi `avatars/{kode}.png` **belum** ditimpa.

Animasi loop belum: generator Arena = 1 frame. Langkah berikutnya: 2–8 frame kedip/napas → WebP animated, atau CSS idle dulu. `prefers-reduced-motion` = still WebP.
