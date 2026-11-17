# Model Directory: Plant Health Detection (`health_inspector`)

Tempatkan file bobot model deteksi kesehatan tanaman kelapa sawit di direktori ini (contoh: `health_model.onnx`, `health_model.pt`, atau `health_model.tflite`).

> **Catatan:** File bobot model diabaikan oleh Git (`.gitignore`) agar repositori tetap ringan. Setelah menempatkan file model di sini, perbarui `weights_path`, `framework`, `input_spec`, dan `labels` di `config/models.yaml`, lalu ubah `is_placeholder: false`.

