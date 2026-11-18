#!/bin/bash
set -e

mkdir -p /root/ComfyUI/user/logs
echo "[INIT-COMFY] Menyiapkan environment ComfyUI bersih..."

# Hapus file kodingan lama secara aman tanpa menyentuh folder models atau user
for f in /root/ComfyUI/*; do
    if [ "$(basename "$f")" != "models" ] && [ "$(basename "$f")" != "user" ]; then
        rm -rf "$f"
    fi
done

if [ -d "/default-comfyui-bundle/ComfyUI" ]; then
    cp -rn /default-comfyui-bundle/ComfyUI/. /root/ComfyUI/
else
    git clone --depth=1 https://github.com/comfyanonymous/ComfyUI.git /tmp/comfy_core
    cp -rn /tmp/comfy_core/. /root/ComfyUI/
    rm -rf /tmp/comfy_core
fi

NODE_DIR="/root/ComfyUI/custom_nodes/ComfyUI-GGUF"
if [ ! -d "$NODE_DIR" ]; then
    echo "[INIT-COMFY] Menginstall plugin ComfyUI-GGUF..."
    git clone https://github.com/city96/ComfyUI-GGUF.git "$NODE_DIR"
    pip install --no-cache-dir -r "$NODE_DIR/requirements.txt"
fi

download_if_missing() {
    local TARGET_DIR=$1
    local FILENAME=$2
    local URL=$3
    mkdir -p "$TARGET_DIR"
    if [ ! -f "$TARGET_DIR/$FILENAME" ]; then
        echo "[INIT-COMFY] Mendownload $FILENAME..."
        aria2c -c -x 8 -s 8 --auto-file-renaming=false -d "$TARGET_DIR" -o "$FILENAME" "$URL"
    else
        echo "[INIT-COMFY] OK: $FILENAME sudah ada di SSD."
    fi
}

download_if_missing "/root/ComfyUI/models/clip" "clip_l.safetensors" \
  "https://huggingface.co/comfyanonymous/flux_text_encoders/resolve/main/clip_l.safetensors"
download_if_missing "/root/ComfyUI/models/clip" "t5xxl_fp8_e4m3fn.safetensors" \
  "https://huggingface.co/comfyanonymous/flux_text_encoders/resolve/main/t5xxl_fp8_e4m3fn.safetensors"
download_if_missing "/root/ComfyUI/models/vae" "ae.safetensors" \
  "https://huggingface.co/ffxvs/vae-flux/resolve/main/ae.safetensors"
download_if_missing "/root/ComfyUI/models/unet" "flux1-kontext-dev-Q4_K_S.gguf" \
  "https://huggingface.co/QuantStack/FLUX.1-Kontext-dev-GGUF/resolve/main/flux1-kontext-dev-Q4_K_S.gguf"

echo "[INIT-COMFY] Memastikan comfy-aimdo tersedia..."
python3 -m pip install --no-cache-dir comfy-aimdo==0.5.6

echo "[INIT-COMFY] Memasang comfy-kitchen yang kompatibel..."
python3 -m pip install --no-cache-dir "comfy-kitchen==0.2.39"

echo "[INIT-COMFY] Menyalakan ComfyUI..."
cd /root/ComfyUI
exec python3 main.py ${CLI_ARGS} 2>&1 | tee -a /root/ComfyUI/user/logs/comfyui.log
