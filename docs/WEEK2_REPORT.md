# Laporan Mingguan 2 (Week 2 Report) — Integrasi Vertical Slice Model AI Pertama

**Proyek:** Low-Cost Multi-Task Smart Inspector System  
**Periode:** Minggu 2 dari 6 Minggu  
**Status:** Selesai & Terverifikasi (Mode Mock Terlabel Jelas — Menunggu File Bobot Model Asli)

---

## 1. Ringkasan Pencapaian Minggu 2

1. **Pemeriksaan Kesiapan Model (`Task A`):**
   - Memeriksa seluruh direktori proyek dan mengonfirmasi bahwa file bobot model terlatih (`.onnx`, `.pt`, `.tflite`) belum tersedia di workspace.
   - Sesuai aturan rekayasa, kami tidak memalsukan model asli. Sebagai gantinya, kami membangun `MockInferenceEngine` yang deterministik dan memberi label `is_mock: true` serta `is_placeholder: true` secara transparan.

2. **Arsitektur Inferensi yang Dapat Digunakan Ulang (`Task B` & `Task C`):**
   - `src/inference/model_loader.py` (`ModelLoader`)
   - `src/inference/preprocessor.py` (`BasePreprocessor`, `StandardImagePreprocessor`, pembaca/penulis citra `.ppm`/`.npy` tanpa ketergantungan eksternal berat, serta dukungan opsional Pillow/OpenCV)
   - `src/inference/inference_engine.py` (`BaseInferenceEngine`, `MockInferenceEngine`, dan `RealModelEngineAdapter` untuk ONNX/PyTorch/TFLite)
   - `src/inference/result_normalizer.py` (`ResultNormalizer` dan validasi `jsonschema`)
   - `src/inference/inference_manager.py` (`InferenceManager` dengan dukungan eksekusi `sequential` dan `parallel` serta pencatatan metrik perangkat keras)
   - Memfokuskan *vertical slice* Minggu 2 pada model kategori ke-5: **Deteksi Kematangan Tandan Buah Segar / TBS (`ripeness_ffb`)**.

3. **Standarisasi Output Inferensi (`Task D`):**
   - Mendefinisikan dan memvalidasi skema JSON `v1.0` yang mencakup `timestamp`, `model_id`, `task_type`, `output_type`, `is_mock`, `status`, `input_dimensions`, `detections`, `confidence`, `bounding_box`, `inference_time_ms`, dan `error`.
   - Mendukung baik model deteksi objek (`bounding_box` berisi `{x_min, y_min, x_max, y_max}`) maupun model klasifikasi (`bounding_box: null`).

4. **Sumber Input Citra Sampel (`Task E`):**
   - Mendukung pemuatan file gambar sampel `tests/assets/sample_palm.ppm` (640x640 RGB) dan pembuatan citra sintetis otomatis jika file sampel belum ada.

---

## 2. Pengukuran Baseline Performa Aktual (`Task F`)

> **Peringatan Penting Mengenai Perangkat Keras:**
> Pengukuran di bawah ini dieksekusi pada **Laptop Pengembangan (Windows 10/11 AMD64)** dalam **Mock Mode** (`MockInferenceEngine` + `StandardImagePreprocessor` NumPy). Hasil ini **BUKAN** merupakan performa Raspberry Pi 5 maupun performa model neural network asli.

### Hasil Pengukuran Aktual (Dieksekusi melalui `.\.venv\Scripts\python.exe -m src.main`):
| Metrik | Nilai Aktual yang Tercatat | Catatan |
| :--- | :--- | :--- |
| **Perangkat Keras Pengujian** | `Windows 10 (AMD64)` — `AMD64 Family 25 Model 80 Stepping 0` | Laptop Pengembangan (Dell G15), `is_raspberry_pi: false` |
| **Mode Runtime & Eksekusi** | `runtime_mode: "mock"`, `execution_mode: "sequential"` | Vertical slice 1 model aktif (`ripeness_ffb`) |
| **Dimensi Citra Input** | `640 x 640 x 3` (RGB) | File `tests/assets/sample_palm.ppm` |
| **Waktu Inisialisasi Model (`load_time_ms`)** | `0.001 ms` | `MockInferenceEngine` (tanpa pemuatan bobot disk besar) |
| **Waktu Inferensi Model (`per_model_inference_ms`)** | `8.26 ms` | Mencakup validasi, resize/normalisasi NumPy 640x640, dan prediksi mock |
| **Total Waktu Siklus (`total_inference_time_ms`)** | `22.479 ms` | Total waktu siklus di `InferenceManager` |
| **Penggunaan Memori Proses (`memory_rss_mb`)** | `56.01 MB` (`0.17%` dari sistem) | Diukur menggunakan `psutil.Process().memory_info().rss` |
| **Penggunaan CPU (`cpu_percent`)** | `9.8%` | Diukur menggunakan `psutil.cpu_percent()` |
| **Jumlah Deteksi (`total_detections`)** | `1` deteksi (`PLACEHOLDER_FFB_RIPE`, confidence `0.768`) | Kandidat kedua (`0.32`) tersaring oleh `confidence_threshold: 0.50` |

### Prosedur Pengujian Performa di Raspberry Pi 5 (Saat Hardware & Model Tersedia):
1. Jalankan `python3 -m src.main` pada Raspberry Pi 5 (8GB RAM).
2. Pastikan field `"is_raspberry_pi": true` muncul secara otomatis pada JSON metrik (dideteksi dari `/proc/device-tree/model`).
3. Bandingkan `total_inference_time_ms` dan `memory_rss_mb` antara `--mode sequential` dan `--mode parallel` ketika kelima model diaktifkan pada Minggu 3–4.

---

## 3. Hasil Pengujian Unit Minggu 2 (`Task G`)

Seluruh **15 unit test** pada `tests/test_config.py`, `tests/test_ros2_poc.py`, dan `tests/test_inference.py` berhasil dijalankan dan **LULUS (15/15 OK dalam 0.897 detik)**, mencakup:
- Pemuatan dan validasi konfigurasi model.
- Validasi citra input (menolak tipe non-array, array kosong, atau jumlah channel salah).
- Preprocessing citra (resize, normalisasi piksel `0..1`, transposisi ke `NCHW`).
- Penyimpanan dan pembacaan file gambar `.ppm`.
- Inferensi mock untuk deteksi objek (`bounding_box` terisi) dan klasifikasi (`bounding_box: null`).
- Normalisasi output dan validasi skema JSON (`jsonschema`).
- Penanganan error eksplisit (model belum dimuat, file bobot model asli tidak ditemukan, dan pemulihan saat gambar input rusak).
- Pencatatan waktu inferensi dan mode eksekusi paralel (`ThreadPoolExecutor`).

