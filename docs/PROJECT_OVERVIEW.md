# Gambaran Umum Proyek — Low-Cost Multi-Task Smart Inspector System

## 1. Latar Belakang & Tujuan Proyek
**Low-Cost Multi-Task Smart Inspector System** adalah sistem inspeksi cerdas berbiaya rendah berbasis **Raspberry Pi 5 (8GB RAM)** yang dirancang untuk mendukung pemantauan perkebunan kelapa sawit secara otomatis. Mengingat konektivitas internet di area perkebunan kelapa sawit sering kali tidak tersedia (*offline*), seluruh proses komputasi inferensi AI, pertukaran pesan antar-node melalui **ROS 2 (DDS)**, serta penyediaan data melalui **API HTTP Lokal** dijalankan secara mandiri di dalam jaringan intranet lokal (LAN/WLAN).

## 2. Batasan Tanggung Jawab (Scope)
Repositori ini mencakup komponen **Companion Computer (AI Inference + ROS 2 + Local Backend Adapter)**:
1. **Integrasi 5 Model AI Kelapa Sawit** pada Raspberry Pi 5:
   - `health_inspector`: Deteksi kesehatan tanaman (*Plant Health Detection*).
   - `pest_detector`: Deteksi indikasi serangan hama (*Pest Indication Detection*).
   - `disease_detector`: Deteksi indikasi penyakit tanaman (*Disease Indication Detection*).
   - `flower_pollination`: Deteksi bunga dan kesiapan penyerbukan (*Flower/Pollination Detection*).
   - `ripeness_ffb`: Deteksi tingkat kematangan Tandan Buah Segar / TBS (*Fresh Fruit Bunch Ripeness Detection*).
2. **Eksekusi Model Terkonfigurasi**: Mendukung mode eksekusi berurutan (`sequential`) maupun paralel (`parallel`).
3. **Integrasi ROS 2**: Mempublikasikan hasil inferensi berformat JSON terstandarisasi ke topik ROS 2 lokal.
4. **Adapter & Kontrak API Lokal**: Menyediakan endpoint REST JSON bagi **Tim Dashboard** terpisah.

> **Di Luar Cakupan (Out of Scope):** Proyek ini **tidak** membangun antarmuka pengguna (UI/Frontend) Dashboard.

## 3. Arsitektur Modular (Peta Jalan 6 Minggu)

```
+-------------------------------------------------------------------------+
|                        SUMBER INPUT CITRA                               |
|  - Minggu 2: File Gambar Sampel (.ppm/.jpg/.png) / Citra Sintetis       |
|  - Minggu 3+: Kamera USB / Stream Kamera Drone                          |
+------------------------------------+------------------------------------+
                                     |
                                     v
+-------------------------------------------------------------------------+
|                  LAPISAN KONFIGURASI & EKSEKUSI                         |
|  - config/settings.yaml & config/models.yaml                            |
|  - src/execution/execution_config.py                                    |
+------------------------------------+------------------------------------+
                                     |
                                     v
+-------------------------------------------------------------------------+
|                  PIPELINE INFERENSI AI (src/inference/)                 |
|  1. StandardImagePreprocessor (Validasi, Resize, Normalisasi NCHW)      |
|  2. ModelLoader -> MockInferenceEngine / RealModelEngineAdapter         |
|  3. InferenceManager (Eksekusi Sequential / Parallel + Telemetri HW)    |
|  4. ResultNormalizer (Validasi JSON Schema v1.0)                        |
+-----------------+-----------------------------------+-------------------+
                  |                                   |
                  v                                   v
+-----------------------------------+   +---------------------------------+
|   INTEGRASI ROS 2 (src/ros2/)     |   |  BACKEND ADAPTER (src/backend/) |
| - InferenceResultPublisher        |   | - Kontrak API: docs/API_CONTRACT|
| - InferenceResultSubscriber       |   | - Minggu 4-5: Local REST Server |
| - Topik: /smart_inspector/...     |   |   untuk Tim Dashboard           |
+-----------------------------------+   +---------------------------------+
```

### Peta Jalan Pengembangan 6 Minggu:
- **Minggu 1 (Selesai):** Inspeksi lingkungan, struktur proyek modular, sistem konfigurasi YAML + validasi, *Proof of Concept* ROS 2 Publisher/Subscriber (dengan isolasi Mock), dan draf kontrak API (`docs/API_CONTRACT.md`).
- **Minggu 2 (Selesai):** Arsitektur komponen inferensi yang dapat digunakan ulang (`ModelLoader`, `BasePreprocessor`, `BaseInferenceEngine`, `ResultNormalizer`, `InferenceManager`), *vertical slice* untuk model pertama (`ripeness_ffb` dalam mode Mock yang tervalidasi penuh karena bobot model asli belum tersedia), skema JSON terstandarisasi, pengujian unit, dan pengukuran *baseline* performa.
- **Minggu 3:** Integrasi file bobot asli untuk kelima model AI kelapa sawit dan penyesuaian *post-processing* spesifik tiap model.
- **Minggu 4:** Optimasi penjadwalan eksekusi sekuensial vs paralel pada CPU ARM Cortex-A76 Raspberry Pi 5 dan manajemen memori.
- **Minggu 5:** Implementasi server HTTP REST API lokal (`src/backend/`) sesuai kontrak API yang telah disepakati bersama Tim Dashboard serta integrasi penuh topik ROS 2 di Ubuntu/Raspberry Pi.
- **Minggu 6:** Pengujian *end-to-end* di Raspberry Pi 5 bersama Tim Dashboard, *profiling* beban kerja lapangan, dan finalisasi dokumentasi Capstone.

