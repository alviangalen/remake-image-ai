#!/bin/bash
set -e

echo "[INIT-COMFY] Mengecek dependensi & custom node ComfyUI-GGUF..."
apt-get update && apt-get install -y --no-install-recommends aria2 git && rm -rf /var/lib/apt/lists/*

# 1. Pasang plugin ComfyUI-GGUF (Wajib untuk baca file .gguf di VRAM 8GB)
NODE_DIR="/root/ComfyUI/custom_nodes/ComfyUI-GGUF"
if [ ! -d "$NODE_DIR" ]; then
    echo "[INIT-COMFY] Menginstall plugin ComfyUI-GGUF..."
    git clone https://github.com/city96/ComfyUI-GGUF.git "$NODE_DIR"
    pip install --no-cache-dir -r "$NODE_DIR/requirements.txt"
fi

# 2. Fungsi auto-download dengan fitur auto-resume (-c)
download_if_missing() {
    local TARGET_DIR=$1
    local FILENAME=$2
    local URL=$3
    mkdir -p "$TARGET_DIR"
    if [ ! -f "$TARGET_DIR/$FILENAME" ]; then
        echo "[INIT-COMFY] Mendownload $FILENAME..."
        aria2c -c -x 8 -s 8 --auto-file-renaming=false -d "$TARGET_DIR" -o "$FILENAME" "$URL"
    else
        echo "[INIT-COMFY] OK: $FILENAME sudah tersedia di SSD."
    fi
}

# 3. Download ke-4 Komponen Wajib Starter Pack
download_if_missing "/root/ComfyUI/models/clip" "clip_l.safetensors" \
  "https://huggingface.co/comfyanonymous/flux_text_encoders/resolve/main/clip_l.safetensors"

download_if_missing "/root/ComfyUI/models/clip" "t5xxl_fp8_e4m3fn.safetensors" \
  "https://huggingface.co/comfyanonymous/flux_text_encoders/resolve/main/t5xxl_fp8_e4m3fn.safetensors"

download_if_missing "/root/ComfyUI/models/vae" "ae.safetensors" \
  "https://huggingface.co/ffxvs/vae-flux/resolve/main/ae.safetensors"

download_if_missing "/root/ComfyUI/models/unet" "flux1-kontext-dev-Q4_K_S.gguf" \
  "https://huggingface.co/QuantStack/FLUX.1-Kontext-dev-GGUF/resolve/main/flux1-kontext-dev-Q4_K_S.gguf"

echo "[INIT-COMFY] Semua model lengkap! Menyalakan mesin ComfyUI..."
python3 /root/ComfyUI/main.py ${CLI_ARGS} 2>&1 | tee -a /root/ComfyUI/user/logs/comfyui.log