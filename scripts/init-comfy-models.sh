#!/bin/bash
set -euo pipefail

MODELS_DIR="/models"
CUSTOM_NODES_DIR="/custom_nodes"
VERIFIED_DIR="${MODELS_DIR}/.verified"

mkdir -p \
  "${MODELS_DIR}/clip" \
  "${MODELS_DIR}/vae" \
  "${MODELS_DIR}/unet" \
  "${VERIFIED_DIR}" \
  "${CUSTOM_NODES_DIR}"

echo "[COMFY-INIT] Memulai pemeriksaan custom node dan model ComfyUI..."

# 1. Pastikan custom node ComfyUI-GGUF tersedia (termasuk jika repo di-clone tanpa submodule)
GGUF_DIR="${CUSTOM_NODES_DIR}/ComfyUI-GGUF"
if [ ! -f "${GGUF_DIR}/nodes.py" ]; then
    echo "[COMFY-INIT] [1/5] Mengunduh custom node ComfyUI-GGUF..."
    rm -rf "${GGUF_DIR}"
    git clone --progress https://github.com/city96/ComfyUI-GGUF.git "${GGUF_DIR}"
else
    echo "[COMFY-INIT] [1/5] OK: ComfyUI-GGUF sudah tersedia."
fi

verify_sha256() {
    local FILE_PATH="$1"
    local EXPECTED_SHA="$2"
    local ACTUAL_SHA
    ACTUAL_SHA="$(sha256sum "${FILE_PATH}" | awk '{print $1}')"
    [ "${ACTUAL_SHA}" = "${EXPECTED_SHA}" ]
}

ensure_model() {
    local STEP="$1"
    local SUBDIR="$2"
    local FILENAME="$3"
    local EXPECTED_BYTES="$4"
    local EXPECTED_SHA="$5"
    local URL="$6"
    local LABEL="$7"

    local TARGET_DIR="${MODELS_DIR}/${SUBDIR}"
    local TARGET_FILE="${TARGET_DIR}/${FILENAME}"
    local PART_FILE="${TARGET_FILE}.part"
    local STAMP_FILE="${VERIFIED_DIR}/${FILENAME}.sha256"

    mkdir -p "${TARGET_DIR}"

    if [ -f "${TARGET_FILE}" ]; then
        local ACTUAL_BYTES
        ACTUAL_BYTES="$(stat -c '%s' "${TARGET_FILE}")"
        if [ "${ACTUAL_BYTES}" = "${EXPECTED_BYTES}" ]; then
            if [ -f "${STAMP_FILE}" ] && [ "$(cat "${STAMP_FILE}")" = "${EXPECTED_SHA}" ]; then
                echo "[COMFY-INIT] ${STEP} OK: ${SUBDIR}/${FILENAME} (${LABEL}) sudah terverifikasi."
                rm -f "${PART_FILE}" "${PART_FILE}.aria2" "${TARGET_FILE}.aria2"
                return 0
            fi
            echo "[COMFY-INIT] ${STEP} Memverifikasi SHA-256 ${SUBDIR}/${FILENAME}..."
            if verify_sha256 "${TARGET_FILE}" "${EXPECTED_SHA}"; then
                echo "${EXPECTED_SHA}" > "${STAMP_FILE}"
                rm -f "${PART_FILE}" "${PART_FILE}.aria2" "${TARGET_FILE}.aria2"
                echo "[COMFY-INIT] ${STEP} OK: ${SUBDIR}/${FILENAME} valid."
                return 0
            fi
        fi
        echo "[COMFY-INIT] ${STEP} WARNING: ${SUBDIR}/${FILENAME} tidak lengkap atau corrupt, mengunduh ulang..."
        rm -f "${TARGET_FILE}" "${TARGET_FILE}.aria2" "${STAMP_FILE}"
    fi

    local ATTEMPT=1
    local MAX_ATTEMPTS=3
    while [ "${ATTEMPT}" -le "${MAX_ATTEMPTS}" ]; do
        echo "[COMFY-INIT] ${STEP} Mengunduh ${SUBDIR}/${FILENAME} (${LABEL}) [Percobaan ${ATTEMPT}/${MAX_ATTEMPTS}]..."
        if aria2c \
            --continue=true \
            --max-connection-per-server=4 \
            --split=4 \
            --min-split-size=8M \
            --file-allocation=none \
            --allow-overwrite=true \
            --auto-file-renaming=false \
            --show-console-readout=false \
            --summary-interval=5 \
            --console-log-level=notice \
            --download-result=hide \
            --max-tries=5 \
            --retry-wait=3 \
            -d "${TARGET_DIR}" \
            -o "${FILENAME}.part" \
            "${URL}"; then

            local PART_BYTES
            PART_BYTES="$(stat -c '%s' "${PART_FILE}" 2>/dev/null || echo 0)"
            if [ "${PART_BYTES}" = "${EXPECTED_BYTES}" ]; then
                echo "[COMFY-INIT] ${STEP} Memverifikasi SHA-256 ${FILENAME}..."
                if verify_sha256 "${PART_FILE}" "${EXPECTED_SHA}"; then
                    mv -f "${PART_FILE}" "${TARGET_FILE}"
                    rm -f "${PART_FILE}.aria2" "${TARGET_FILE}.aria2"
                    echo "${EXPECTED_SHA}" > "${STAMP_FILE}"
                    echo "[COMFY-INIT] ${STEP} Selesai & terverifikasi: ${SUBDIR}/${FILENAME}"
                    return 0
                fi
            fi
            echo "[COMFY-INIT] ${STEP} ERROR: Ukuran/SHA-256 ${FILENAME} tidak cocok (bytes=${PART_BYTES}), menghapus file parsial..."
            rm -f "${PART_FILE}" "${PART_FILE}.aria2"
        else
            echo "[COMFY-INIT] ${STEP} ERROR: Koneksi terputus saat mengunduh ${FILENAME}, mencoba lanjutkan..."
        fi

        ATTEMPT=$((ATTEMPT + 1))
        sleep 2
    done

    echo "[COMFY-INIT] FATAL: Gagal mengunduh ${SUBDIR}/${FILENAME} secara valid setelah ${MAX_ATTEMPTS} percobaan." >&2
    exit 1
}

ensure_model "[2/5]" "clip" "clip_l.safetensors" \
    "246144152" \
    "660c6f5b1abae9dc498ac2d21e1347d2abdb0cf6c0c0c8576cd796491d9a6cdd" \
    "https://huggingface.co/comfyanonymous/flux_text_encoders/resolve/main/clip_l.safetensors" \
    "~235 MB"

ensure_model "[3/5]" "vae" "ae.safetensors" \
    "335304388" \
    "afc8e28272cd15db3919bacdb6918ce9c1ed22e96cb12c4d5ed0fba823529e38" \
    "https://huggingface.co/ffxvs/vae-flux/resolve/main/ae.safetensors" \
    "~320 MB"

ensure_model "[4/5]" "clip" "t5xxl_fp8_e4m3fn.safetensors" \
    "4893934904" \
    "7d330da4816157540d6bb7838bf63a0f02f573fc48ca4d8de34bb0cbfd514f09" \
    "https://huggingface.co/comfyanonymous/flux_text_encoders/resolve/main/t5xxl_fp8_e4m3fn.safetensors" \
    "~4.6 GB"

ensure_model "[5/5]" "unet" "flux1-kontext-dev-Q4_K_S.gguf" \
    "6797337888" \
    "cc22ff7a2debb02e63765fa53af8c5ae0b6883b462d0601b9b55f51a15cdd6da" \
    "https://huggingface.co/QuantStack/FLUX.1-Kontext-dev-GGUF/resolve/main/flux1-kontext-dev-Q4_K_S.gguf" \
    "~6.4 GB"

echo "[COMFY-INIT] Semua custom node dan model ComfyUI lengkap & terverifikasi!"
