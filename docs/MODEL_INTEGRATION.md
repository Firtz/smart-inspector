# Panduan Integrasi Model AI — Smart Inspector System

Dokumen ini menjelaskan arsitektur komponen inferensi yang dibangun pada Minggu 2, cara kerja **Mock Mode**, serta daftar spesifikasi teknis dan langkah-langkah yang dibutuhkan untuk mengintegrasikan **5 model AI kelapa sawit asli** ketika file bobot model telah tersedia.

---

## 1. Status Kesiapan Model Saat Ini (Minggu 2)

Berdasarkan pemeriksaan direktori kerja (`d:\kuliah\Capstone\smart-inspector`), saat ini **belum terdapat file bobot model terlatih** (`.onnx`, `.pt`, `.pth`, atau `.tflite`) maupun file daftar label kelas asli.

Sesuai aturan rekayasa proyek:
1. Kami **tidak memalsukan** file bobot model atau mengklaim inferensi model asli telah berjalan.
2. Seluruh entri di `config/models.yaml` ditandai secara eksplisit dengan `is_placeholder: true` dan `framework: "mock"`, serta nama kelas diberi awalan `PLACEHOLDER_`.
3. Kami mengimplementasikan `MockInferenceEngine` yang menghasilkan prediksi deterministik berdasarkan isi tensor input sehingga seluruh alur kerja (*input validation* → *preprocessing* → *inference* → *result normalization* → *ROS 2 publishing* → *performance telemetry*) dapat dieksekusi dan diuji secara *end-to-end*.

---

## 2. Arsitektur Komponen Inferensi (`src/inference/`)

Kelima model AI menggunakan antarmuka komponen yang sama sehingga penambahan model ke-2 hingga ke-5 pada Minggu 3 tidak memerlukan perombakan kode:

1. **`StandardImagePreprocessor` (`src/inference/preprocessor.py`)**:
   - Memvalidasi tipe, dimensi (`HxWxC`), dan channel citra input (`validate_image`).
   - Melakukan konversi ruang warna (`RGB` ↔ `BGR`), pengubahan ukuran (*resize*) sesuai `input_spec` masing-masing model, penskalaan piksel (`0_to_1` atau `0_to_255`), normalisasi `mean`/`std`, serta transposisi ke tensor `NCHW` (`(1, C, H, W)` `float32`).
2. **`BaseInferenceEngine`, `MockInferenceEngine`, & `RealModelEngineAdapter` (`src/inference/inference_engine.py`)**:
   - Menyediakan siklus hidup seragam: `load()`, `predict(preprocessed)`, dan `unload()`.
   - `MockInferenceEngine` membedakan antara model deteksi objek (`output_type: "object_detection"`, menghasilkan `bounding_box` piksel) dan model klasifikasi (`output_type: "classification"`, menghasilkan `bounding_box: None`).
   - `RealModelEngineAdapter` memeriksa keberadaan file bobot di disk dan memuat sesi runtime (`onnxruntime`, `tflite_runtime`, atau `torch`). Jika file bobot tidak ditemukan, akan melempar `ModelLoadError` secara eksplisit.
3. **`ModelLoader` (`src/inference/model_loader.py`)**:
   - Factory yang memilih antara `MockInferenceEngine` atau `RealModelEngineAdapter` berdasarkan `runtime_mode` (`mock` vs `real`) dan konfigurasi model.
4. **`ResultNormalizer` (`src/inference/result_normalizer.py`)**:
   - Menyaring prediksi di bawah `confidence_threshold`, mengurutkan berdasarkan `confidence` tertinggi, dan memvalidasi hasil akhir terhadap **JSON Schema (`INFERENCE_RESULT_JSON_SCHEMA`)**.
   - Menyediakan metode `normalize_error()` agar kegagalan validasi input atau kegagalan runtime tetap menghasilkan JSON berformat standar (`status: "error"`).
5. **`InferenceManager` (`src/inference/inference_manager.py`)**:
   - Mengelola pemuatan model aktif, mengeksekusi siklus inspeksi baik dalam mode `sequential` maupun `parallel` (`ThreadPoolExecutor`), serta merekam metrik perangkat keras (`psutil`).

---

## 3. Skema Output Inferensi Terstandarisasi (`v1.0`)

Setiap hasil inferensi divalidasi terhadap skema berikut:

### Contoh 1: Model Deteksi Objek (`ripeness_ffb` — Memiliki `bounding_box`)
```json
{
  "schema_version": "1.0",
  "timestamp": "2026-11-12T10:57:28.600130+00:00",
  "model_id": "ripeness_ffb",
  "task_type": "ffb_ripeness",
  "output_type": "object_detection",
  "is_mock": true,
  "status": "success",
  "input_dimensions": {
    "width": 640,
    "height": 640,
    "channels": 3
  },
  "detections": [
    {
      "label": "PLACEHOLDER_FFB_RIPE",
      "class_id": 1,
      "confidence": 0.768,
      "bounding_box": {
        "x_min": 128,
        "y_min": 115,
        "x_max": 480,
        "y_max": 512
      }
    }
  ],
  "confidence": 0.768,
  "bounding_box": {
    "x_min": 128,
    "y_min": 115,
    "x_max": 480,
    "y_max": 512
  },
  "inference_time_ms": 8.26,
  "error": null
}
```

### Contoh 2: Model Klasifikasi (`health_inspector` — `bounding_box` Bernilai `null`)
```json
{
  "schema_version": "1.0",
  "timestamp": "2026-11-12T10:57:28.610000+00:00",
  "model_id": "health_inspector",
  "task_type": "plant_health",
  "output_type": "classification",
  "is_mock": true,
  "status": "success",
  "input_dimensions": {
    "width": 640,
    "height": 640,
    "channels": 3
  },
  "detections": [
    {
      "label": "PLACEHOLDER_HEALTHY",
      "class_id": 0,
      "confidence": 0.85,
      "bounding_box": null
    }
  ],
  "confidence": 0.85,
  "bounding_box": null,
  "inference_time_ms": 3.12,
  "error": null
}
```

### Contoh 3: Respons Ketika Terjadi Error Validasi / Inferensi
```json
{
  "schema_version": "1.0",
  "timestamp": "2026-11-12T10:57:28.620000+00:00",
  "model_id": "ripeness_ffb",
  "task_type": "ffb_ripeness",
  "output_type": "object_detection",
  "is_mock": true,
  "status": "error",
  "input_dimensions": {
    "width": 1,
    "height": 1,
    "channels": 3
  },
  "detections": [],
  "confidence": null,
  "bounding_box": null,
  "inference_time_ms": 0.05,
  "error": {
    "code": "INVALID_INPUT_IMAGE",
    "message": "Input citra kosong (size == 0)."
  }
}
```

---

## 4. Daftar Informasi yang Wajib Disediakan untuk Integrasi Model Asli

Untuk menggantikan placeholder dengan model asli (dimulai dari 1 model pertama pada *vertical slice*), siapkan data berikut untuk setiap model:

| Parameter | Contoh Nilai | Keterangan |
| :--- | :--- | :--- |
| **1. File Bobot Model** | `models/ripeness/ffb_yolov8n.onnx` | Disarankan format **ONNX (`.onnx`)** atau **TFLite (`.tflite`)** untuk efisiensi CPU di Raspberry Pi 5. |
| **2. Framework & Arsitektur** | `onnx` (YOLOv8n / MobileNetV3 / ResNet18) | Menentukan cara decoding tensor keluaran (*post-processing*). |
| **3. Jenis Output (`output_type`)** | `object_detection` atau `classification` | Menentukan apakah model menghasilkan `bounding_box` atau hanya skor kelas. |
| **4. Resolusi & Format Input** | `640x640`, `RGB`, `scale: 0_to_1` | Resolusi `width x height`, urutan kanal warna (`RGB`/`BGR`), serta nilai `mean` dan `std`. |
| **5. Daftar Urutan Label Kelas** | `["unripe", "ripe", "overripe"]` | Urutan indeks kelas (`0..N-1`) yang persis sama dengan saat pelatihan (*training*). |
| **6. Bentuk Tensor Output** | Contoh: `[1, 7, 8400]` atau `[1, 3]` | Diperlukan untuk mengimplementasikan fungsi *post-processing* di `RealModelEngineAdapter.predict()`. |

---

## 5. Langkah-Langkah Mengaktifkan Model Asli Pertama

1. Salin file bobot model (misal `ripeness.onnx`) ke dalam folder `models/ripeness/`.
2. Buka `config/models.yaml` pada bagian `ripeness_ffb`, lalu perbarui:
   - `is_placeholder: false`
   - `framework: "onnx"` (atau `"pytorch"` / `"tflite"`)
   - `weights_path: "models/ripeness/ripeness.onnx"`
   - `input_spec`: sesuaikan `width`, `height`, `color_format`, `mean`, `std`.
   - `labels`: masukkan daftar nama kelas asli.
3. Buka `config/settings.yaml` dan ubah `runtime_mode: "real"` (atau set variabel lingkungan `SMART_INSPECTOR_RUNTIME_MODE=real`).
4. Sesuaikan *tensor decoding* pada metode `RealModelEngineAdapter.predict()` di `src/inference/inference_engine.py` sesuai bentuk tensor output model tersebut.
5. Jalankan pengujian:
   ```powershell
   .\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py" -v
   .\.venv\Scripts\python.exe -m src.main
   ```

