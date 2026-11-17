# Draf Kontrak API Lokal — Smart Inspector System (`v1`)

**Status Dokumen:** Draf Awal (Minggu 1 — Untuk Diskusi dengan Tim Dashboard)  
**Target Host:** Raspberry Pi 5 (8GB RAM) pada Jaringan Intranet Lokal  
**Protokol:** HTTP/1.1 REST JSON (Tanpa Ketergantungan Internet Publik)  
**Base URL Default:** `http://<IP_RASPBERRY_PI>:8000/api/v1`

---

## 1. Tujuan dan Ruang Lingkup

Dokumen ini mendefinisikan draf kontrak komunikasi antarmuka pemrograman aplikasi (API) antara:
1. **Sistem Backend/Companion Smart Inspector (Tim AI & ROS 2):** Berjalan di atas Raspberry Pi 5, mengeksekusi hingga 5 model AI deteksi kelapa sawit (sekuensial maupun paralel), mempublikasikan hasil ke topik ROS 2, dan menyediakan endpoint HTTP lokal.
2. **Sistem Dashboard Pemantauan (Tim Dashboard):** Aplikasi terpisah yang mengambil (*polling* / *request*) status perangkat, daftar model, dan hasil deteksi terbaru melalui jaringan lokal untuk divisualisasikan kepada pengguna.

> **Batasan Ruang Lingkup:** Modul ini **hanya** menyediakan data JSON melalui REST API lokal dan topik ROS 2. Pengembangan antarmuka grafis (UI/Frontend) sepenuhnya berada di bawah tanggung jawab Tim Dashboard.

---

## 2. Asumsi Jaringan Intranet Lokal (Kebun Kelapa Sawit)

Mengingat lokasi operasional di perkebunan kelapa sawit sering kali **tidak memiliki koneksi internet**:
1. **Jaringan Tertutup (Offline-First):** Seluruh komunikasi berlangsung di jaringan lokal (LAN kabel Ethernet atau Wi-Fi Access Point lokal antara Raspberry Pi 5, Drone/Rover, dan perangkat klien Dashboard).
2. **Alamat IP Statis / mDNS:** Raspberry Pi 5 direkomendasikan menggunakan IP statis pada subnet lokal (misal `192.168.10.50`) atau hostname mDNS (`smart-inspector.local`).
3. **Tanpa Autentikasi Cloud Eksternal:** Endpoint tidak boleh bergantung pada OAuth/Auth0 berbasis internet. Jika diperlukan pengamanan dasar di intranet, dapat digunakan header `X-API-Key` statis yang dikonfigurasi melalui `.env`.
4. **Sinkronisasi Waktu:** Apabila tidak ada server NTP internet, timestamp menggunakan waktu sistem lokal Raspberry Pi 5 dalam format **ISO-8601 UTC** (`YYYY-MM-DDTHH:MM:SS.ffffff+00:00`).
5. **CORS:** Header `Access-Control-Allow-Origin: *` akan diaktifkan untuk memudahkan konsumsi dari aplikasi web dashboard di jaringan lokal.

---

## 3. Daftar Endpoint yang Diusulkan

| Metode | Endpoint | Deskripsi Singkat |
| :--- | :--- | :--- |
| `GET` | `/api/v1/health` | Pemeriksaan cepat (*liveness check*) apakah layanan API aktif. |
| `GET` | `/api/v1/status` | Status operasional sistem, mode eksekusi, status node ROS 2, dan metrik sumber daya (CPU/RAM). |
| `GET` | `/api/v1/models` | Daftar 5 model AI yang terdaftar beserta status aktif/nonaktif dan spesifikasi inputnya. |
| `GET` | `/api/v1/results/latest` | Hasil inferensi paling mutakhir dari model yang aktif (satu siklus inspeksi terakhir). |
| `GET` | `/api/v1/results` | Riwayat hasil inferensi terakhir yang tersimpan di *in-memory buffer* (mendukung filter query). |

---

## 4. Spesifikasi Endpoint dan Contoh Respons JSON

### 4.1. `GET /api/v1/health`
Memastikan server backend di Raspberry Pi 5 dapat dihubungi.

**Respons Sukses (`200 OK`):**
```json
{
  "status": "ok",
  "service": "smart_inspector_companion",
  "version": "0.2.0",
  "timestamp": "2026-11-12T08:30:00.123456+00:00"
}
```

---

### 4.2. `GET /api/v1/status`
Memberikan informasi kondisi perangkat keras dan konfigurasi eksekusi saat ini.

**Respons Sukses (`200 OK`):**
```json
{
  "status": "running",
  "timestamp": "2026-11-12T08:30:05.000000+00:00",
  "node_name": "smart_inspector_companion",
  "environment": "production",
  "runtime_mode": "mock",
  "execution_mode": "sequential",
  "ros2": {
    "available": false,
    "enabled": false,
    "node_name": "smart_inspector_inference_node",
    "topic_inference_results": "/smart_inspector/inference/results"
  },
  "enabled_models": [
    "ripeness_ffb"
  ],
  "system_metrics": {
    "cpu_percent": 24.5,
    "memory_used_mb": 612.4,
    "memory_percent": 7.6
  }
}
```

---

### 4.3. `GET /api/v1/models`
Mengembalikan daftar kelima kategori model AI beserta status kesiapannya.

**Respons Sukses (`200 OK`):**
```json
{
  "total_models": 5,
  "active_count": 1,
  "models": [
    {
      "model_id": "health_inspector",
      "name": "Plant Health Detection Model",
      "task_type": "plant_health",
      "output_type": "classification",
      "enabled": false,
      "is_placeholder": true,
      "framework": "mock",
      "input_spec": {
        "width": 224,
        "height": 224,
        "channels": 3,
        "color_format": "RGB"
      },
      "confidence_threshold": 0.5,
      "labels": [
        "PLACEHOLDER_HEALTHY",
        "PLACEHOLDER_NUTRIENT_DEFICIENT",
        "PLACEHOLDER_WATER_STRESSED"
      ]
    },
    {
      "model_id": "ripeness_ffb",
      "name": "Fresh Fruit Bunch (FFB/TBS) Ripeness Model",
      "task_type": "ffb_ripeness",
      "output_type": "object_detection",
      "enabled": true,
      "is_placeholder": true,
      "framework": "mock",
      "input_spec": {
        "width": 640,
        "height": 640,
        "channels": 3,
        "color_format": "RGB"
      },
      "confidence_threshold": 0.5,
      "labels": [
        "PLACEHOLDER_FFB_UNRIPE",
        "PLACEHOLDER_FFB_RIPE",
        "PLACEHOLDER_FFB_OVERRIPE"
      ]
    }
  ]
}
```

---

### 4.4. `GET /api/v1/results/latest`
Mengembalikan hasil inferensi terbaru untuk setiap model yang aktif atau satu bundel siklus inspeksi terakhir.

**Respons Sukses (`200 OK`):**
```json
{
  "cycle_id": "cycle_20261112_083010_001",
  "execution_mode": "sequential",
  "total_cycle_time_ms": 18.42,
  "results": [
    {
      "schema_version": "1.0",
      "timestamp": "2026-11-12T08:30:10.450123+00:00",
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
          "confidence": 0.912,
          "bounding_box": {
            "x_min": 120,
            "y_min": 80,
            "x_max": 420,
            "y_max": 390
          }
        }
      ],
      "confidence": 0.912,
      "bounding_box": {
        "x_min": 120,
        "y_min": 80,
        "x_max": 420,
        "y_max": 390
      },
      "inference_time_ms": 15.8,
      "error": null
    }
  ]
}
```

> **Catatan Penting mengenai `bounding_box`:**
> Tidak semua model menghasilkan kotak pembatas (*bounding box*). Model dengan `output_type: "classification"` (seperti `health_inspector`) akan memiliki `"bounding_box": null` baik pada level root maupun pada setiap item di dalam `detections`. Tim Dashboard wajib memeriksa apakah `bounding_box` bernilai `null` sebelum menggambar overlay kotak pada UI.

---

### 4.5. `GET /api/v1/results`
Mengambil daftar riwayat hasil inferensi terakhir dari memori.

**Parameter Query Opsional:**
- `limit` (integer, default `20`, maks `100`): Jumlah item maksimum yang dikembalikan.
- `model_id` (string, opsional): Filter berdasarkan ID model tertentu (contoh: `?model_id=ripeness_ffb`).
- `task_type` (string, opsional): Filter berdasarkan jenis tugas (contoh: `?task_type=ffb_ripeness`).

**Respons Sukses (`200 OK`):**
```json
{
  "count": 1,
  "limit": 20,
  "filters": {
    "model_id": "ripeness_ffb",
    "task_type": null
  },
  "items": [
    {
      "schema_version": "1.0",
      "timestamp": "2026-11-12T08:30:10.450123+00:00",
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
          "confidence": 0.912,
          "bounding_box": {
            "x_min": 120,
            "y_min": 80,
            "x_max": 420,
            "y_max": 390
          }
        }
      ],
      "confidence": 0.912,
      "bounding_box": {
        "x_min": 120,
        "y_min": 80,
        "x_max": 420,
        "y_max": 390
      },
      "inference_time_ms": 15.8,
      "error": null
    }
  ]
}
```

---

## 5. Deskripsi Field Skema Hasil Inferensi

| Nama Field | Tipe Data | Nullable? | Deskripsi |
| :--- | :--- | :--- | :--- |
| `schema_version` | `string` | Tidak | Versi skema output terstandarisasi (saat ini `"1.0"`). |
| `timestamp` | `string` (ISO-8601) | Tidak | Waktu selesai inferensi dalam format UTC ISO-8601. |
| `model_id` | `string` | Tidak | ID unik model di `config/models.yaml` (mis. `"ripeness_ffb"`). |
| `task_type` | `string` | Tidak | Kategori tugas (`plant_health`, `pest_indication`, `disease_indication`, `flower_pollination`, `ffb_ripeness`). |
| `output_type` | `string` | Tidak | Jenis keluaran model (`classification`, `object_detection`, `segmentation`). |
| `is_mock` | `boolean` | Tidak | Bernilai `true` jika dihasilkan oleh `MockInferenceEngine`, `false` jika dari model AI asli. |
| `status` | `string` | Tidak | `"success"` jika inferensi berhasil, atau `"error"` jika gagal. |
| `input_dimensions` | `object` | Tidak | Dimensi citra input asal (`width`, `height`, `channels`). |
| `detections` | `array<object>` | Tidak | Daftar deteksi di atas ambang batas (*confidence threshold*). Bisa berupa list kosong `[]` jika tidak ada objek terdeteksi. |
| `detections[].label` | `string` | Tidak | Nama label kelas hasil prediksi. |
| `detections[].class_id` | `integer` | Tidak | Indeks kelas numerik (`0..N-1`). |
| `detections[].confidence` | `number` (`float`) | Tidak | Nilai keyakinan prediksi (`0.0` hingga `1.0`). |
| `detections[].bounding_box` | `object` \| `null` | **Ya** | Koordinat piksel `{x_min, y_min, x_max, y_max}` untuk deteksi objek, atau `null` untuk model klasifikasi. |
| `confidence` | `number` \| `null` | **Ya** | Nilai `confidence` tertinggi dari daftar `detections` (ringkasan cepat), atau `null` jika tidak ada deteksi/error. |
| `bounding_box` | `object` \| `null` | **Ya** | `bounding_box` dari deteksi dengan `confidence` tertinggi, atau `null` jika klasifikasi / tidak ada deteksi. |
| `inference_time_ms` | `number` (`float`) | Tidak | Durasi eksekusi inferensi dalam milidetik (`>= 0.0`). |
| `error` | `object` \| `null` | **Ya** | Bernilai `null` saat `status == "success"`. Berisi `{code, message}` saat `status == "error"`. |

---

## 6. Format Respons Error Standar

Seluruh kegagalan HTTP (4xx / 5xx) menggunakan struktur JSON yang seragam:

```json
{
  "status": "error",
  "timestamp": "2026-11-12T08:35:00.000000+00:00",
  "error": {
    "code": "MODEL_NOT_FOUND",
    "message": "Model dengan ID 'unknown_model' tidak terdaftar pada sistem.",
    "details": {
      "requested_model_id": "unknown_model",
      "available_models": [
        "health_inspector",
        "pest_detector",
        "disease_detector",
        "flower_pollination",
        "ripeness_ffb"
      ]
    }
  }
}
```

**Kode Status HTTP Standar:**
- `200 OK`: Permintaan berhasil.
- `400 Bad Request`: Parameter query tidak valid (mis. `limit` negatif).
- `404 Not Found`: Endpoint atau `model_id` tidak ditemukan.
- `503 Service Unavailable`: Pipeline inferensi sedang dalam proses inisialisasi atau mengalami kegagalan kritis.

---

## 7. Daftar Pertanyaan untuk Disepakati Bersama Tim Dashboard

Sebelum implementasi server API di Minggu 4–5 dikunci, poin-poin berikut perlu disepakati bersama Tim Dashboard:

1. **Mekanisme Pengambilan Data:** Apakah Tim Dashboard cukup menggunakan *HTTP Polling* berkala (misal setiap 1–2 detik ke `GET /api/v1/results/latest`), atau membutuhkan *Server-Sent Events (SSE)* / *WebSocket*?
2. **Penyertaan Gambar / Thumbnail:** Apakah Dashboard hanya membutuhkan metadata JSON deteksi (koordinat bounding box & label), atau memerlukan endpoint terpisah untuk mengambil frame gambar terakhir (misal `GET /api/v1/frame/latest` dalam bentuk JPEG atau Base64)? *(Catatan: Mengirim gambar penuh di setiap JSON akan membebani bandwidth Wi-Fi lokal dan RAM Raspberry Pi 5).*
3. **Kontrol Konfigurasi dari Dashboard (Write API):** Apakah Dashboard hanya bersifat *Read-Only* (memantau hasil), atau pengguna Dashboard perlu mengubah mode eksekusi (`sequential` ↔ `parallel`) dan mengaktifkan/menonaktifkan model secara dinamis melalui endpoint `POST`/`PATCH`?
4. **Sistem Koordinat Bounding Box:** Apakah Tim Dashboard lebih memilih koordinat piksel absolut (`x_min, y_min, x_max, y_max` terhadap resolusi input) atau koordinat ternormalisasi (`0.0`–`1.0`) agar mudah di-render pada ukuran layar apa pun?
5. **Penyimpanan Riwayat Lokal:** Berapa banyak riwayat hasil inferensi yang perlu dipertahankan di memori Raspberry Pi 5 jika koneksi Wi-Fi ke laptop Dashboard sempat terputus sementara di kebun?

