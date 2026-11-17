# Panduan Pengaturan Lingkungan Pengembangan & Deployment Raspberry Pi 5

Dokumen ini memisahkan dengan tegas antara **Lingkungan Pengembangan Host (Laptop Windows)** dan **Lingkungan Runtime Target (Raspberry Pi 5 — Linux & ROS 2)**.

---

## 1. Hasil Inspeksi Lingkungan Saat Ini (Host Development)

Berdasarkan pemeriksaan aktual pada mesin pengembangan saat proyek diinisialisasi:
- **Sistem Operasi Host:** Microsoft Windows 10/11 (`Windows NT 10.0.26300.0`, arsitektur `AMD64`).
- **Prosesor Host:** `AMD64 Family 25 Model 80 Stepping 0, AuthenticAMD` (Laptop Dell G15).
- **Versi Python:** `Python 3.11.9` (`pip 24.0`).
- **Versi Git:** `git version 2.48.1.windows.1`.
- **Ketersediaan ROS 2 di Host:** **Tidak tersedia** (`ros2` CLI dan paket `rclpy` tidak terpasang; WSL belum memiliki distribusi Linux yang terinstal).
- **Paket Python yang Sudah Tersedia:** `PyYAML 6.0.1`, `numpy 2.3.2`, `psutil 5.9.8`, `jsonschema 4.21.1`.

Karena pengembangan dilakukan di Windows tanpa instalasi ROS 2 maupun bobot model AI asli, proyek dirancang agar dapat berjalan 100% di dalam *virtual environment* (`.venv`) menggunakan **Mock Mode** (`runtime_mode: "mock"` dan `ros2.enabled: false`), sementara seluruh kode ROS 2 (`rclpy`) tetap disiapkan dan terisolasi di dalam `src/ros2/`.

---

## 2. Pengaturan Lingkungan Pengembangan di Windows (Host)

### 2.1. Membuat Virtual Environment Terisolasi (`.venv`)
Disarankan menggunakan flag `--system-site-packages` jika berada di jaringan tanpa internet agar dapat memanfaatkan paket `numpy`, `PyYAML`, `psutil`, dan `jsonschema` yang sudah ada di sistem:

```powershell
# Dari direktori root proyek: d:\kuliah\Capstone\smart-inspector
python -m venv .venv --system-site-packages
```

Jika terhubung ke internet dan ingin menginstal ulang seluruh dependensi dari `requirements.txt`:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

### 2.2. Menjalankan Aplikasi & Pengujian di Windows
```powershell
# Menjalankan seluruh unit test (15 pengujian)
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py" -v

# Menjalankan pipeline utama (Mock Inference + Mock ROS 2 Pub/Sub)
.\.venv\Scripts\python.exe -m src.main
```

---

## 3. Rekomendasi Distribusi ROS 2 untuk Raspberry Pi 5 (Target Runtime)

Jangan menebak distribusi ROS 2 sebelum memeriksa sistem operasi Linux yang terpasang di Raspberry Pi 5. Gunakan matriks kompatibilitas resmi (**REP-2000**) berikut:

| Sistem Operasi pada Raspberry Pi 5 (64-bit `aarch64`) | Distribusi ROS 2 yang Direkomendasikan | Cara Instalasi Terbaik | Masa Dukungan (EOL) |
| :--- | :--- | :--- | :--- |
| **Ubuntu Server / Desktop 24.04 LTS (Noble Numbat)** *(Sangat Direkomendasikan untuk RPi 5)* | **ROS 2 Jazzy Jalisco** (LTS) | Paket Debian Native (`apt install ros-jazzy-ros-base`) | Mei 2029 |
| **Ubuntu 22.04 LTS (Jammy Jellyfish)** | **ROS 2 Humble Hawksbill** (LTS) | Paket Debian Native (`apt install ros-humble-ros-base`) | Mei 2027 |
| **Raspberry Pi OS (64-bit, berbasis Debian 12 Bookworm)** | **ROS 2 Jazzy** atau **ROS 2 Humble** | Melalui **Docker Container** (`ros:jazzy-ros-base` / `ros:humble-ros-base`) atau kompilasi dari sumber | Sesuai image LTS |

> **Catatan Teknis Penting untuk Raspberry Pi 5:**
> Kernel dan firmware bootloader Raspberry Pi 5 didukung secara resmi (*first-class support*) mulai **Ubuntu 24.04 LTS (Noble)**. Oleh karena itu, kombinasi **Ubuntu 24.04 LTS 64-bit + ROS 2 Jazzy Jalisco** adalah pilihan paling stabil karena menyediakan paket `apt` `arm64` siap pakai tanpa perlu kompilasi sumber atau overhead Docker.

---

## 4. Prosedur Deployment & Pengujian di Raspberry Pi 5

Setelah papan Raspberry Pi 5 siap dengan Ubuntu 24.04 LTS (atau 22.04 LTS):

### Langkah 1: Periksa Versi OS di Raspberry Pi 5
```bash
lsb_release -a
uname -m  # Pastikan menampilkan aarch64
```

### Langkah 2: Instalasi ROS 2 (Contoh pada Ubuntu 24.04 LTS — ROS 2 Jazzy)
```bash
sudo apt update && sudo apt install -y locales curl gnupg lsb-release
sudo locale-gen en_US en_US.UTF-8
sudo update-locale LC_ALL=en_US.UTF-8 LANG=en_US.UTF-8

sudo curl -sSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.key -o /usr/share/keyrings/ros-archive-keyring.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] http://packages.ros.org/ros2/ubuntu $(. /etc/os-release && echo $UBUNTU_CODENAME) main" | sudo tee /etc/apt/sources.list.d/ros2.list > /dev/null

sudo apt update
sudo apt install -y ros-jazzy-ros-base python3-venv python3-pip
echo "source /opt/ros/jazzy/setup.bash" >> ~/.bashrc
source /opt/ros/jazzy/setup.bash
```

### Langkah 3: Kloning Proyek & Buat Virtual Environment di Raspberry Pi 5
Penting: Gunakan `--system-site-packages` saat membuat `.venv` di Raspberry Pi 5 agar paket `rclpy` dan `std_msgs` dari `/opt/ros/<distro>/` dapat diakses di dalam `.venv`:

```bash
git clone <URL_REPO_ANDA> smart-inspector
cd smart-inspector
python3 -m venv .venv --system-site-packages
source .venv/bin/activate
pip install -r requirements.txt
```

### Langkah 4: Menguji ROS 2 Publisher & Subscriber Proof of Concept secara Native
Buka **Terminal 1** di Raspberry Pi 5 (Publisher):
```bash
source /opt/ros/jazzy/setup.bash
source .venv/bin/activate
python3 -m src.ros2.publisher
```

Buka **Terminal 2** di Raspberry Pi 5 (Subscriber):
```bash
source /opt/ros/jazzy/setup.bash
source .venv/bin/activate
python3 -m src.ros2.subscriber
```

### Langkah 5: Mengonfigurasi Intranet Lokal (DDS Discovery Tanpa Internet)
Di kebun kelapa sawit tanpa internet, pastikan semua perangkat di LAN yang sama menggunakan `ROS_DOMAIN_ID` yang sama:
```bash
export ROS_DOMAIN_ID=42
export ROS_AUTOMATIC_DISCOVERY_RANGE=SUBNET
```

