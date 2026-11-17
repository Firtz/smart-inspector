# Placeholder Backend & Adapter API Lokal (`src/backend/`)

Direktori ini disiapkan untuk implementasi **Python Backend Adapter & Local HTTP API** yang akan dikonsumsi oleh tim Dashboard terpisah melalui jaringan intranet lokal (LAN/Wi-Fi kebun kelapa sawit).

## Cakupan Minggu 1 – Minggu 2
Sesuai jadwal pengembangan 6 minggu:
- **Minggu 1–2**: Merancang dan menyepakati draf kontrak API (`docs/API_CONTRACT.md`) serta menstandarisasi skema output inferensi JSON (`src/inference/result_normalizer.py`). Tidak mengimplementasikan server HTTP/UI yang belum diperlukan.
- **Minggu 3–4**: Mengintegrasikan seluruh model (sekuensial & paralel) dengan *ring buffer* state di memori (`src/backend/`).
- **Minggu 5–6**: Mengaktifkan server HTTP lokal (`GET /api/v1/health`, `/api/v1/status`, `/api/v1/models`, `/api/v1/results/latest`, `/api/v1/results`) dan pengujian integrasi dengan tim Dashboard di Raspberry Pi 5.

Lihat dokumen lengkap kontrak API di [`docs/API_CONTRACT.md`](../../docs/API_CONTRACT.md).

