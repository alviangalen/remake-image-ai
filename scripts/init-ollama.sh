#!/bin/sh
echo "[INIT-OLLAMA] Menyalakan service Ollama..."
/bin/ollama serve &
PID=$!

# Tunggu hingga daemon Ollama siap menerima perintah
i=0
while ! ollama list >/dev/null 2>&1; do
    i=$((i + 1))
    if [ "$i" -ge 30 ]; then
        echo "[INIT-OLLAMA] ERROR: Service Ollama gagal merespons." >&2
        exit 1
    fi
    sleep 1
done

MODEL_NAME="${LLM_MODEL:-qwen2.5:7b}"
echo "[INIT-OLLAMA] Mengecek ketersediaan model ${MODEL_NAME}..."
if ! ollama list | grep -Fq "${MODEL_NAME}"; then
    echo "[INIT-OLLAMA] Model belum ada di SSD! Memulai auto-pull ${MODEL_NAME}..."
    ollama pull "${MODEL_NAME}"
    echo "[INIT-OLLAMA] Download ${MODEL_NAME} selesai!"
else
    echo "[INIT-OLLAMA] Model ${MODEL_NAME} sudah tersedia, siap digunakan!"
fi

wait $PID