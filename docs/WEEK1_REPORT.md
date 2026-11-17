# Laporan Mingguan 1 (Week 1 Report) — Fondasi Lingkungan & Proyek

**Proyek:** Low-Cost Multi-Task Smart Inspector System  
**Periode:** Minggu 1 dari 6 Minggu  
**Status:** Selesai & Terverifikasi  

---

## 1. Ringkasan Pencapaian Minggu 1

Seluruh objektif Minggu 1 telah diselesaikan dan diverifikasi:

1. **Inspeksi Lingkungan Pengembangan (`Task A`):**
   - Mengidentifikasi mesin pengembangan saat ini sebagai **Windows 10/11 (AMD64)** dengan **Python 3.11.9** dan **Git 2.48.1.windows.1**.
   - Mengonfirmasi bahwa **ROS 2 (`rclpy`) belum terpasang** di host Windows saat ini.
   - Memisahkan dengan tegas konfigurasi pengembangan host Windows dari target runtime Linux pada Raspberry Pi 5 (`docs/ENVIRONMENT_SETUP.md`).
   - Menyusun rekomendasi distribusi ROS 2 berdasarkan kompatibilitas resmi REP-2000 (Ubuntu 24.04 LTS → **ROS 2 Jazzy Jalisco**; Ubuntu 22.04 LTS → **ROS 2 Humble Hawksbill**).

2. **Struktur Proyek Modular (`Task B`):**
   - Membangun hierarki direktori yang bersih dan mudah dipelihara: `config/`, `models/` (5 subdirektori tugas AI), `src/inference/`, `src/execution/`, `src/ros2/`, `src/backend/`, `tests/`, dan `docs/`.
   - Menyiapkan `.gitignore` agar bobot model berukuran besar, `.venv`, dan file rahasia (`.env`) tidak ikut ter-commit ke Git.

3. **Manajemen Konfigurasi (`Task C`):**
   - Membuat `config/settings.yaml` dan `config/models.yaml` dengan dokumentasi lengkap pada setiap field.
   - Mengimplementasikan `src/execution/execution_config.py` menggunakan dataclass bertipe kuat (`AppConfig`, `ModelConfig`, `ExecutionSettings`, `ROS2Settings`, `APISettings`) beserta validasi nilai dan dukungan override melalui environment variable (`.env.example`).

4. **Proof of Concept ROS 2 Publisher & Subscriber (`Task D`):**
   - Mengimplementasikan `src/ros2/publisher.py` (`InferenceResultPublisher`) dan `src/ros2/subscriber.py` (`InferenceResultSubscriber`) menggunakan tipe pesan standar `std_msgs/msg/String` berisi payload JSON.
   - Mengisolasi impor `rclpy` sehingga kode dapat dijalankan dan diuji pada lingkungan tanpa ROS 2 menggunakan saluran callback Mock lokal, sekaligus siap dijalankan secara native di Raspberry Pi 5 begitu ROS 2 di-source.

5. **Draf Kontrak API Lokal (`Task E`):**
   - Menyusun `docs/API_CONTRACT.md` untuk didiskusikan bersama Tim Dashboard.
   - Mencakup spesifikasi endpoint (`GET /api/v1/health`, `/status`, `/models`, `/results/latest`, `/results`), contoh respons JSON, deskripsi field, format error standar, asumsi jaringan intranet kebun kelapa sawit tanpa internet, serta daftar pertanyaan teknis untuk disepakati dengan Tim Dashboard.

---

## 2. Verifikasi & Hasil Pengujian Minggu 1

Pengujian dijalankan di dalam *virtual environment* terisolasi (`.venv`) menggunakan perintah:
```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py" -v
```

- **`tests/test_config.py` (5 pengujian):** **LULUS (OK)** — Memastikan pemuatan `settings.yaml` dan `models.yaml`, override variabel lingkungan, serta penolakan konfigurasi yang rusak/tidak valid.
- **`tests/test_ros2_poc.py` (2 pengujian):** **LULUS (OK)** — Memastikan pengiriman dan penerimaan pesan JSON inferensi pada loop Publisher → Subscriber dalam mode Mock, serta penanganan error JSON yang rusak. *(Pengujian ROS 2 native menggunakan daemon DDS `rclpy` ditandai **Pending pada Target Raspberry Pi 5** dengan instruksi reproduksi lengkap di `docs/ENVIRONMENT_SETUP.md`).*

