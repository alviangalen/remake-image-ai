# AGENTS.md — Victus AI Studio Context & Guardrails

## 1. Spesifikasi Environment Aktif (JANGAN DIUBAH KE VERSI LAMA)
- **Hardware:** HP Victus (Ryzen 9 8945HS + RTX 4060 8GB VRAM + 16GB DDR5 + 120GB Ext SSD)
- **ComfyUI Image:** `yanwk/comfyui-boot:cu130-slim-v2` (Python 3.13, PyTorch 2.13.0+cu130)
- **Pre-start Script:** Hanya memeriksa Python, PyTorch, dan `comfy_aimdo.control`. DILARANG menambahkan `apt-get`, `find`, atau instalasi pip yang merusak dependensi bawaan image.
- **Custom Nodes:** `city96/ComfyUI-GGUF` di-mount langsung dari host `custom_nodes/ComfyUI-GGUF` ke container.
- **Workflow Path:** File workflow aktif berada di `/app/flux_edit.json` (`backend/app/flux_edit.json`).

## 2. Aturan VRAM & Workflow FLUX.1 Kontext
1. Gunakan `VRAMGuard` (`async with guard.lock:`) di setiap operasi GPU.
2. Workflow `flux_edit.json` WAJIB menggunakan node `ReferenceLatent` (Node `"41"`), `FluxGuidance` (Node `"35"`), dan `FluxKontextImageScale` (Node `"42"`), dengan `KSampler` `denoise: 1.0` agar identitas wajah dan background gambar asli tidak berubah.
3. Prompt edit wajib dalam Bahasa Inggris (diterjemahkan otomatis via Ollama `qwen2.5:7b` sebelum dikirim ke ComfyUI).
