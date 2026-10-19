#!/bin/bash
set -e

echo "[INIT-COMFY] Mengecek kelengkapan custom node GGUF & model..."
apt-get update && apt-get install -y aria2 git

# 1. Pasang ComfyUI-GGUF node jika belum ada (Wajib buat jalanin model Q4 di 8GB VRAM)
NODE_DIR="/root/ComfyUI/custom_nodes/ComfyUI-GGUF"
if [ ! -d "$NODE_DIR" ]; then
    echo "[INIT-COMFY] Menginstall plugin ComfyUI-GGUF..."
    git clone https://github.com/city96/ComfyUI-GGUF.git "$NODE_DIR"
    pip install --no-cache-dir -r "$NODE_DIR/requirements.txt"
fi

# 2. Fungsi auto-download dengan fitur Resume (-c)
download_if_missing() {
    local TARGET_DIR=$1
    local FILENAME=$2
    local URL=$3
    mkdir -p "$TARGET_DIR"
    if [ ! -f "$TARGET_DIR/$FILENAME" ]; then
        echo "[INIT-COMFY] Mendownload $FILENAME..."
        aria2c -c -x 8 -s 8 -d "$TARGET_DIR" -o "$FILENAME" "$URL"
    else
        echo "[INIT-COMFY] $FILENAME sudah ada, lewati download."
    fi
}

# Contoh Auto-Download VAE & CLIP ringan (Link HuggingFace)
download_if_missing "/root/ComfyUI/models/clip" "clip_l.safetensors" \
  "https://huggingface.co/comfyanonymous/flux_text_encoders/resolve/main/clip_l.safetensors"

download_if_missing "/root/ComfyUI/models/clip" "t5xxl_fp8_e4m3fn.safetensors" \
  "https://huggingface.co/comfyanonymous/flux_text_encoders/resolve/main/t5xxl_fp8_e4m3fn.safetensors"

echo "[INIT-COMFY] Semua siap! Menyalakan ComfyUI Engine..."
python3 /root/ComfyUI/main.py ${CLI_ARGS} 2>&1 | tee -a /root/ComfyUI/user/logs/comfyui.log