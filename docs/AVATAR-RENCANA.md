# Rencana avatar MIRAI

**Aktif:** donghua modern / AI agent, dewasa muda, bust, pakaian gelap, latar ink. Bukan foto, clipart, robot chrome, wajah tua.

## Pack (2026-10-16)

Produksi: `mission-control/web/avatars/{kode}.webp`  
Master: `avatars/_new/{kode}.png`  
API: `GET /api/avatars/pack?code=tr` (webp dulu, png cadangan).

| kode | file | kursi |
|------|------|--------|
| TR | tr.webp | General / inbox |
| RS | rs.webp | Research |
| BD | bd.webp | Builder |
| QA | qa.webp | QA |
| KR | kr.webp | Kreator |
| SB | sb.webp | Serbaguna |
| AS | as.webp | ASN |
| CR | cr.webp | Cron |
| ED | ed.webp | Edu |
| OR | or.webp | Orkestrator |

WebP **animated** (6 frame napas). Still: `{kode}-still.webp` via `?still=1`. Dashboard pakai still jika `prefers-reduced-motion: reduce`.

## Wiring

Roster → `avatar.url` → `seatCard` / mosaik. Library/upload/reset di `avatars.py`.
