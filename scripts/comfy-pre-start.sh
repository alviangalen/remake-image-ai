#!/bin/bash
set -eu

export PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
PYTHON="/usr/bin/python3.12"
GGUF_DIR="/root/ComfyUI/custom_nodes/ComfyUI-GGUF"
REQ_FILE="$GGUF_DIR/requirements.txt"

echo "[PRE-START] Python: $("$PYTHON" -c 'import sys; print(sys.executable)')"
echo "[PRE-START] PyTorch: $("$PYTHON" -c 'import torch; print(torch.__version__)')"

"$PYTHON" -c 'import comfy_aimdo.control'
echo "[PRE-START] comfy-aimdo: OK"

if [ ! -f "$GGUF_DIR/nodes.py" ]; then
    echo "[PRE-START] ERROR: ComfyUI-GGUF tidak ditemukan."
    exit 1
fi

if ! "$PYTHON" -c 'import gguf, sentencepiece, google.protobuf' >/dev/null 2>&1; then
    echo "[PRE-START] Memasang dependensi GGUF..."
    "$PYTHON" -m pip install -r "$REQ_FILE"
fi

"$PYTHON" -c 'import gguf, sentencepiece, google.protobuf'
echo "[PRE-START] Dependensi GGUF: OK"
echo "[PRE-START] Pemeriksaan selesai."
