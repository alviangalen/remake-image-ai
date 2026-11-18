# AI Studio — Local Image Editing & LLM Orchestrator

Aplikasi web lokal untuk **AI Image Editing** berbasis **FLUX.1 Kontext (GGUF)** dan **LLM Chat** berbasis **Ollama (`qwen2.5:7b`)** yang diorkestrasi menggunakan FastAPI dan Docker Compose, dirancang khusus agar berjalan stabil pada GPU **8 GB VRAM** tanpa bentrok memori (*Zero-Conflict VRAM Swapping*).

---

## Fitur Utama

- **Instruction-Based Image Editing (FLUX.1 Kontext Dev Q4_K_S)**
  Mengubah warna, pakaian, objek, atau latar belakang gambar sesuai instruksi teks sambil mempertahankan identitas wajah, pose, pencahayaan, dan komposisi asli melalui arsitektur node resmi `FluxKontextImageScale` → `VAEEncode` → `ReferenceLatent` → `FluxGuidance` → `EmptySD3LatentImage`.
- **Auto-Translate Prompt (Indonesia → Inggris)**
  Instruksi edit dalam Bahasa Indonesia otomatis dideteksi dan diterjemahkan ke Bahasa Inggris yang presisi menggunakan Ollama (`qwen2.5:7b`) sebelum diproses oleh ComfyUI.
- **Progress Bar & ETA Real-Time**
  Memantau setiap tahap pemrosesan gambar secara langsung (`uploading`, `translating`, `loading_models`, `conditioning`, `sampling step/total`, `decoding`, `saving`) lengkap dengan persentase, durasi berjalan, dan estimasi sisa waktu.
- **LLM Chat dengan Token Streaming Real-Time**
  Respons LLM dikirim token demi token (`application/x-ndjson` + `ReadableStream` tanpa buffering Nginx) sehingga teks langsung tampil bertahap saat model menghasilkan jawaban.
- **Zero-Conflict VRAM Guard**
  `VRAMGuard` mengunci operasi GPU secara bergantian (`asyncio.Lock`) dan otomatis mengosongkan VRAM engine lawan sebelum berpindah antara Ollama dan ComfyUI, lalu mengembalikan GPU ke kondisi `IDLE` setelah proses selesai.
- **Kontrol Parameter & Preview Before/After**
  Tersedia slider `Denoise` (`0.30–1.00`), `Guidance` (`1.5–5.0`), input `Seed` opsional, tombol **Tahan: Lihat Asli**, unduh hasil PNG, tombol **Flush VRAM**, dan **Live Log**.

---

## Minimum Requirements (Target: NVIDIA RTX 4060 8 GB VRAM)

Sistem ini dioptimalkan untuk dijalankan pada GPU consumer kelas **8 GB VRAM** dengan konfigurasi offload memori (`--lowvram --reserve-vram 0.5`).

### Spesifikasi Hardware Minimum

| Komponen | Minimum | Rekomendasi |
| :--- | :--- | :--- |
| **GPU** | **NVIDIA GeForce RTX 4060 (8 GB VRAM)** atau GPU NVIDIA setara dengan **8 GB VRAM** | NVIDIA GPU ≥ 8 GB VRAM (arsitektur Ampere / Ada Lovelace atau lebih baru) |
| **RAM Sistem** | **16 GB** | **32 GB** (membantu offloading layer T5-XXL & UNet saat sampling) |
| **Storage (SSD)** | **40 GB** ruang kosong (NVMe/SATA SSD) | **60 GB+** NVMe SSD |
| **CPU** | x86_64 **6 Core / 12 Thread** | **8 Core / 16 Thread** |

> **Rincian Kebutuhan Storage (~32–36 GB):**
> - Model ComfyUI (`models/comfyui/`): **~12 GB** (`flux1-kontext-dev-Q4_K_S.gguf` `6.4 GB`, `t5xxl_fp8_e4m3fn.safetensors` `4.6 GB`, `ae.safetensors` `320 MB`, `clip_l.safetensors` `235 MB`).
> - Model Ollama (`models/ollama/`): **~4.7 GB** (`qwen2.5:7b`).
> - Docker Images (`comfyui-boot`, `ollama`, `python:3.11-slim`, `node:20-alpine`, `nginx:alpine`) + build cache: **~15–20 GB**.

### Spesifikasi Software & Driver

| Komponen | Kebutuhan | Catatan |
| :--- | :--- | :--- |
| **Sistem Operasi** | Linux (Ubuntu / Debian) atau Windows WSL2 | Disarankan Linux native untuk manajemen GPU & I/O Docker terbaik |
| **NVIDIA Driver** | **≥ 550.xx** | Teruji stabil pada Driver **550.163.01** dengan image ComfyUI `yanwk/comfyui-boot:cu126-slim` (CUDA 12.6 / Python 3.12) |
| **Docker** | Docker Engine + **Docker Compose v2+** | Gunakan versi modern yang mendukung `deploy.resources.reservations.devices` |
| **GPU Runtime** | **NVIDIA Container Toolkit** (`nvidia-ctk`) | Wajib agar container `ollama` dan `comfyui` bisa mengakses GPU NVIDIA |
| **Utilities** | `git`, `curl`, `make` (opsional) | Untuk clone custom node, download model, dan menjalankan shortcut `Makefile` |

> **Catatan Kompatibilitas CUDA Driver:**  
> [`docker-compose.yml`](docker-compose.yml) menggunakan `yanwk/comfyui-boot:cu126-slim` yang kompatibel dengan NVIDIA Driver **550.xx** ke atas. Jika Anda berencana mengganti image ComfyUI ke tag CUDA yang lebih tinggi (misalnya `cu130`), pastikan NVIDIA Driver host sudah diperbarui mengikuti kebutuhan CUDA image tersebut.

---

## Arsitektur Layanan

```text
Browser (http://localhost:3000)
   │
   ▼
[frontend] React + Vite + Tailwind + Nginx Reverse Proxy (:3000 -> :80)
   │  (proxy_buffering off untuk streaming LLM & upload gambar hingga 50MB)
   ▼
[backend] FastAPI + VRAMGuard (:8000)
   ├──► [ollama]       qwen2.5:7b (:11434)          ── Auto-pull LLM, Streaming Chat & Auto-Translate
   └──► [comfyui]      ComfyUI + GGUF (:8188)       ── FLUX.1 Kontext Image Editing
           ▲
           │ (selesai & terverifikasi SHA-256 sebelum ComfyUI berjalan)
        [comfyui-init] Auto-download ComfyUI-GGUF + 4 model FLUX.1 Kontext
```

---

## Struktur Direktori

```text
.
├── .env.example                 # Template konfigurasi port dan nama model
├── docker-compose.yml           # Definisi service (ollama, comfyui-init, comfyui, backend, frontend)
├── Makefile                     # Shortcut operasional (up, down, status, logs, flush, clean-disk)
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt         # FastAPI 0.115.0, Uvicorn, httpx, websockets, Pillow
│   └── app/
│       ├── main.py              # REST API, job queue progress, dan SSE/NDJSON chat stream
│       ├── vram_manager.py      # VRAMGuard lock & auto-flush Ollama/ComfyUI
│       ├── flux_edit.json       # Workflow API resmi FLUX.1 Kontext
│       └── services/
│           ├── comfy_svc.py     # Upload, preprocessing PNG, WebSocket progress, Eksekusi workflow
│           └── ollama_svc.py    # Deteksi bahasa & translasi prompt ke Bahasa Inggris
├── frontend/
│   ├── Dockerfile               # Multi-stage build (node:20-alpine -> nginx:alpine)
│   ├── nginx.conf               # Konfigurasi proxy non-buffered untuk /api/
│   ├── package.json             # React 18, Vite 5, Tailwind CSS 3, Lucide Icons
│   └── src/
│       ├── App.jsx              # Antarmuka Image Edit Studio & LLM Chat
│       └── api/client.js        # Client API polling progress & NDJSON stream reader
├── custom_nodes/
│   └── ComfyUI-GGUF/            # Custom node loader model GGUF untuk ComfyUI (auto-clone jika kosong)
├── models/
│   ├── comfyui/                 # Direktori model ComfyUI (auto-download + verifikasi SHA-256)
│   └── ollama/                  # Penyimpanan model Ollama
└── scripts/
    ├── init-comfy-models.sh     # Auto-download & verifikasi SHA-256 ComfyUI-GGUF + 4 model FLUX.1 Kontext
    ├── comfy-pre-start.sh       # Pemeriksaan dependensi Python, PyTorch, comfy_aimdo, & GGUF
    └── init-ollama.sh           # Auto-pull model LLM saat container Ollama dijalankan
```

---

## Panduan Instalasi & Menjalankan Project (Satu Perintah)

Seluruh custom node (`ComfyUI-GGUF`), model **ComfyUI**, dan model **Ollama** diunduh dan diverifikasi secara otomatis saat container dinyalakan — tidak perlu mengunduh file model satu per satu secara manual.

### 1. Clone Repository & Siapkan `.env`

```bash
git clone <url-repository-anda> remake-image-ai
cd remake-image-ai
cp .env.example .env
```

Isi bawaan `.env.example`:

```env
FRONTEND_PORT=3000
BACKEND_PORT=8000
COMFY_PORT=8188

LLM_MODEL=qwen2.5:7b
IMAGE_MODEL_NAME=flux1-kontext-dev-Q4_K_S.gguf
```

### 2. Jalankan Aplikasi (Auto-Download + Progres CLI → Otomatis ke Background)

```bash
make up
```

Atau langsung menggunakan Docker Compose:

```bash
chmod +x scripts/*.sh
docker compose up --build --wait --wait-timeout 7200
```

Yang terjadi secara otomatis dalam satu perintah tersebut:
1. Mem-build image `backend` dan `frontend`.
2. Menjalankan `comfyui-init` dan `ollama` secara paralel serta **menampilkan progres unduhan langsung di CLI**:
   - `comfyui-init` otomatis mengecek/meng-clone `ComfyUI-GGUF`, mengunduh 4 model ComfyUI dengan dukungan *resume* (`aria2c`), dan memverifikasi ukuran byte serta **SHA-256** sebelum memindahkannya ke folder aktif (sehingga file tidak pernah corrupt jika internet sempat terputus).
   - `ollama` otomatis melakukan `ollama pull` untuk `qwen2.5:7b`.
3. Setelah semua unduhan selesai dan seluruh service berstatus `healthy`, perintah CLI otomatis selesai (`exit 0`) dan seluruh container tetap berjalan normal di latar belakang (*background*).
4. Pada start berikutnya, pengecekan model langsung melewati tahap download dalam hitungan detik selama file sudah terverifikasi.

Setelah siap, akses melalui browser:
- **Web UI Utama:** `http://localhost:3000`
- **Backend FastAPI Docs:** `http://localhost:8000/docs`
- **ComfyUI Dashboard:** `http://localhost:8188`

### Daftar Model yang Diunduh Otomatis

| Komponen | Lokasi Tujuan | Ukuran | Sumber |
| :--- | :--- | :--- | :--- |
| `ComfyUI-GGUF` | `custom_nodes/ComfyUI-GGUF/` | — | [city96/ComfyUI-GGUF](https://github.com/city96/ComfyUI-GGUF) |
| `clip_l.safetensors` | `models/comfyui/clip/` | ~235 MB | [comfyanonymous/flux_text_encoders](https://huggingface.co/comfyanonymous/flux_text_encoders/resolve/main/clip_l.safetensors) |
| `ae.safetensors` | `models/comfyui/vae/` | ~320 MB | [ffxvs/vae-flux](https://huggingface.co/ffxvs/vae-flux/resolve/main/ae.safetensors) |
| `t5xxl_fp8_e4m3fn.safetensors` | `models/comfyui/clip/` | ~4.6 GB | [comfyanonymous/flux_text_encoders](https://huggingface.co/comfyanonymous/flux_text_encoders/resolve/main/t5xxl_fp8_e4m3fn.safetensors) |
| `flux1-kontext-dev-Q4_K_S.gguf` | `models/comfyui/unet/` | ~6.4 GB | [QuantStack/FLUX.1-Kontext-dev-GGUF](https://huggingface.co/QuantStack/FLUX.1-Kontext-dev-GGUF/resolve/main/flux1-kontext-dev-Q4_K_S.gguf) |
| `qwen2.5:7b` | `models/ollama/` | ~4.7 GB | Ollama Registry (`ollama pull`) |

---

## Panduan Penggunaan & Tips Prompting FLUX.1 Kontext

### Pengaturan Parameter yang Disarankan

- **Denoise (`1.00` — Default):** Pertahankan di **`1.00`** untuk hasil terbaik. Workflow `flux_edit.json` menggunakan `EmptySD3LatentImage` sebagai kanvas sampling sambil menyalurkan gambar asli melalui `ReferenceLatent`, sehingga `denoise = 1.0` wajib dipakai agar proses difusi selesai penuh tanpa meninggalkan noise/distorsi.
- **Guidance (`2.5` — Default):** Rentang ideal untuk mengikuti instruksi sekaligus menjaga kemiripan gambar asli (`2.0 – 3.5`).
- **Seed:** Kosongkan untuk hasil acak tiap eksekusi, atau isi angka tetap jika ingin hasil yang konsisten/reproducible saat membandingkan variasi prompt.

### Pola Prompt Efektif

Sebutkan dengan jelas **apa yang diubah** dan **apa yang harus dipertahankan**:

- **Bahasa Inggris (Langsung ke ComfyUI):**
  - `"Change only the white dress to vivid red. Preserve the original background, face, hair, pose, lighting, and composition."`
  - `"Change only the background to a sunset beach. Keep the person, face, clothing, and pose unchanged."`
- **Bahasa Indonesia (Otomatis diterjemahkan oleh `qwen2.5:7b`):**
  - `"Ubah warna gaun menjadi merah menyala, pertahankan wajah, rambut, pose, pencahayaan, dan latar belakang asli."`
  - `"Ganti latar belakang menjadi suasana kafe malam yang hangat tanpa mengubah orang dan pakaiannya."`

---

## Endpoint API Utama

| Method | Endpoint | Deskripsi |
| :--- | :--- | :--- |
| `GET` | `/api/health` | Status kesehatan `ollama`, `comfyui`, serta pemilik VRAM aktif (`IDLE` / `OLLAMA` / `COMFY`) |
| `POST` | `/api/chat/stream` | Chat LLM dengan streaming NDJSON token demi token (`prompt` via form-data) |
| `POST` | `/api/chat` | Chat LLM mode non-streaming (mengembalikan JSON penuh) |
| `POST` | `/api/edit-image/jobs` | Memulai job edit gambar asinkron dan mengembalikan `job_id` |
| `GET` | `/api/edit-image/jobs/{job_id}` | Polling progres, step sampling, waktu berjalan, dan ETA job |
| `GET` | `/api/edit-image/jobs/{job_id}/result` | Mengunduh hasil akhir PNG beserta header metadata (`X-Seed`, `X-Guidance`, `X-Denoise`, `X-Steps`, `X-Prompt`, `X-Elapsed-Seconds`) |
| `POST` | `/api/edit-image` | Endpoint edit gambar sinkron (langsung mengembalikan PNG) |
| `POST` | `/api/flush` | Mengosongkan VRAM dari Ollama dan ComfyUI secara manual |

---

## Perintah Operasional & Troubleshooting

```bash
make up          # Build & jalankan semua container di background
make down        # Hentikan semua container
make status      # Cek status container, /api/health, dan penggunaan VRAM via nvidia-smi
make logs        # Pantau log seluruh container secara live
make flush       # Kuras paksa VRAM ComfyUI & restart service LLM
make clean-disk  # Bersihkan cache build Docker tanpa menghapus model AI
```

### Masalah Umum

1. **Container ComfyUI gagal mengakses GPU / error driver CUDA:**  
   Pastikan `nvidia-smi` terbaca di host, NVIDIA Container Toolkit sudah aktif (`nvidia-ctk runtime configure --runtime=docker`), dan driver NVIDIA kompatibel dengan `yanwk/comfyui-boot:cu126-slim`.
2. **Gambar hasil edit tampak tidak mengikuti prompt / bercak noise:**  
   - Pastikan parameter **Denoise** bernilai **`1.00`**.
   - Verifikasi file `models/comfyui/clip/clip_l.safetensors` (`~235 MB`) dan `t5xxl_fp8_e4m3fn.safetensors` (`~4.6 GB`) sudah terunduh utuh (tidak ada sisa file `.aria2` atau ukuran jauh lebih kecil dari semestinya).
3. **Out of Memory (OOM) pada GPU 8 GB VRAM:**  
   Tutup aplikasi lain yang memakai VRAM besar saat rendering berjalan, atau klik tombol **Flush VRAM** pada UI sebelum memulai proses baru.
