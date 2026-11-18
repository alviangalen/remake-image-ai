#!/bin/sh
echo "[INIT-OLLAMA] Menyalakan service Ollama..."
/bin/ollama serve &
PID=$!
sleep 4

echo "[INIT-OLLAMA] Mengecek ketersediaan model ${LLM_MODEL:-qwen2.5:7b}..."
if ! ollama list | grep -q "${LLM_MODEL:-qwen2.5:7b}"; then
    echo "[INIT-OLLAMA] Model belum ada di SSD! Memulai auto-pull..."
    ollama pull "${LLM_MODEL:-qwen2.5:7b}"
    echo "[INIT-OLLAMA] Download selesai!"
else
    echo "[INIT-OLLAMA] Model sudah tersedia, siap digunakan!"
fi

wait $PID