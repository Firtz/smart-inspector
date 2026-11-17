# Low-Cost Multi-Task Smart Inspector System

Fondasi perangkat lunak **Minggu 1 & Minggu 2** untuk proyek Capstone **Low-Cost Multi-Task Smart Inspector System** pada **Raspberry Pi 5 (8GB RAM)** menggunakan **Python** dan **ROS 2**.

Sistem ini dirancang untuk mengeksekusi **5 tugas deteksi AI kelapa sawit** (secara sekuensial maupun paralel), mempublikasikan hasil inferensi ke jaringan lokal **ROS 2 (DDS)**, dan menyediakan **API HTTP lokal** bagi tim Dashboard terpisah di lingkungan perkebunan kelapa sawit tanpa koneksi internet.

---

## Fitur Fondasi Minggu 1 & Minggu 2
- **5 Kategori Tugas AI Kelapa Sawit Terdaftar (`config/models.yaml`)**:
  1. `health_inspector` — Deteksi kesehatan tanaman (*Classification*).
  2. `pest_detector` — Deteksi indikasi hama (*Object Detection*).
  3. `disease_detector` — Deteksi indikasi penyakit (*Object Detection*).
  4. `flower_pollination` — Deteksi bunga/penyerbukan (*Object Detection*).
  5. `ripeness_ffb` — Deteksi kematangan Tandan Buah Segar / TBS (*Object Detection* — **Fokus Vertical Slice Minggu 2**).
- **Komponen Inferensi Modular (`src/inference/`)**: `ModelLoader`, `StandardImagePreprocessor`, `BaseInferenceEngine`, `MockInferenceEngine`, `RealModelEngineAdapter`, `ResultNormalizer` (dengan validasi `jsonschema`), dan `InferenceManager`.
- **Mode Eksekusi Terkonfigurasi**: Mendukung mode `sequential` dan `parallel` serta `mock` dan `real`.
- **Isolasi ROS 2 (`src/ros2/`)**: Publisher & Subscriber menggunakan `rclpy` (`std_msgs/msg/String`) yang otomatis beralih ke saluran simulasi lokal jika dijalankan di laptop Windows tanpa instalasi ROS 2.
- **Draf Kontrak API Lokal (`docs/API_CONTRACT.md`)**: Spesifikasi endpoint REST JSON untuk didiskusikan dengan Tim Dashboard.

---

## Struktur Direktori

```text
smart-inspector/
├── config/
│   ├── settings.yaml                  # Konfigurasi sistem, eksekusi, input, ROS 2, dan API
│   └── models.yaml                    # Registri 5 model AI kelapa sawit (placeholder terlabel)
├── models/
│   ├── health/README.md               # Folder bobot model kesehatan tanaman
│   ├── pest/README.md                 # Folder bobot model indikasi hama
│   ├── disease/README.md              # Folder bobot model indikasi penyakit
│   ├── flower/README.md               # Folder bobot model bunga/penyerbukan
│   └── ripeness/README.md             # Folder bobot model kematangan TBS/FFB
├── src/
│   ├── execution/
│   │   ├── __init__.py
│   │   └── execution_config.py        # Pemuat & validator konfigurasi YAML + env override
│   ├── inference/
│   │   ├── __init__.py
│   │   ├── model_loader.py            # Factory pemuat engine Mock vs Real
│   │   ├── preprocessor.py            # Validasi citra, pembaca PPM/NPY/PIL, & normalisasi NCHW
│   │   ├── inference_engine.py        # BaseInferenceEngine, MockInferenceEngine, RealModelEngineAdapter
│   │   ├── result_normalizer.py       # Standarisasi output JSON & validasi JSON Schema v1.0
│   │   └── inference_manager.py       # Orkestrator sekuensial/paralel & telemetri performa HW
│   ├── ros2/
│   │   ├── __init__.py
│   │   ├── publisher.py               # ROS 2 Publisher POC (dengan fallback mock)
│   │   └── subscriber.py              # ROS 2 Subscriber POC (dengan fallback mock)
│   ├── backend/
│   │   ├── __init__.py
│   │   └── api_contract_placeholder.md
│   ├── __init__.py
│   └── main.py                        # Entrypoint utama aplikasi
├── tests/
│   ├── assets/
│   │   └── sample_palm.ppm            # Citra sampel pengujian (640x640 RGB)
│   ├── __init__.py
│   ├── test_config.py                 # Unit test pemuatan & validasi konfigurasi
│   ├── test_ros2_poc.py               # Unit test ROS 2 Publisher/Subscriber POC
│   └── test_inference.py              # Unit test preprocessing, inferensi, normalisasi, & error handling
├── docs/
│   ├── PROJECT_OVERVIEW.md            # Arsitektur & peta jalan 6 minggu
│   ├── ENVIRONMENT_SETUP.md           # Panduan setup Windows vs Raspberry Pi 5 + ROS 2
│   ├── API_CONTRACT.md                # Draf kontrak API lokal untuk Tim Dashboard
│   ├── MODEL_INTEGRATION.md           # Panduan integrasi model AI asli & skema output
│   ├── WEEK1_REPORT.md                # Laporan penyelesaian Minggu 1
│   └── WEEK2_REPORT.md                # Laporan penyelesaian & baseline performa Minggu 2
├── .env.example                       # Contoh variabel lingkungan
├── .gitignore                         # Mengabaikan bobot model, .venv, cache, dan log
├── requirements.txt                   # Daftar dependensi Python
└── README.md
```

---

## Cara Instalasi & Menjalankan Proyek

### 1. Menyiapkan Virtual Environment (`.venv`)
Pada Windows PowerShell:
```powershell
python -m venv .venv --system-site-packages
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

### 2. Menjalankan Aplikasi Utama
```powershell
# Menjalankan vertical slice default (sequential, mock mode)
.\.venv\Scripts\python.exe -m src.main

# Menjalankan dengan override mode paralel melalui argumen CLI
.\.venv\Scripts\python.exe -m src.main --mode parallel
```

### 3. Menjalankan ROS 2 Proof of Concept
```powershell
# Publisher POC
.\.venv\Scripts\python.exe -m src.ros2.publisher

# Subscriber POC
.\.venv\Scripts\python.exe -m src.ros2.subscriber
```

### 4. Menjalankan Seluruh Unit Test
```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py" -v
```

---

## Dokumentasi Lengkap
- [Gambaran Umum Proyek & Peta Jalan 6 Minggu](docs/PROJECT_OVERVIEW.md)
- [Pengaturan Lingkungan Windows & Deployment Raspberry Pi 5](docs/ENVIRONMENT_SETUP.md)
- [Draf Kontrak API Lokal untuk Tim Dashboard](docs/API_CONTRACT.md)
- [Panduan Integrasi Model AI & Skema Output](docs/MODEL_INTEGRATION.md)
- [Laporan Minggu 1](docs/WEEK1_REPORT.md)
- [Laporan Minggu 2](docs/WEEK2_REPORT.md)

