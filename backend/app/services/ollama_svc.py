import logging
import re
import httpx

_INDONESIAN_MARKERS = {
    "ubah", "ganti", "gantikan", "jadikan", "menjadi", "jadi", "warna",
    "baju", "gaun", "pakaian", "celana", "jaket", "rok", "kerudung",
    "topi", "sepatu", "rambut", "wajah", "muka", "kulit", "mata", "tangan",
    "latar", "belakang", "pemandangan", "pantai", "senja", "malam", "pagi",
    "siang", "sore", "hutan", "kota", "gedung", "ruangan", "kamar", "langit",
    "awan", "laut", "gunung", "cahaya", "bayangan", "pencahayaan", "tetap",
    "pertahankan", "jaga", "jangan", "tanpa", "hapus", "hilangkan",
    "tambahkan", "tambah", "buat", "dengan", "yang", "dan", "atau", "ke",
    "dari", "di", "pada", "untuk", "saja", "hanya", "semua", "lainnya",
    "selain", "asli", "merah", "biru", "putih", "hitam", "hijau", "kuning",
    "ungu", "coklat", "abu", "jingga", "oranye", "gelap", "terang", "cerah",
    "menyala", "elegan", "sambil", "agar", "supaya", "seperti", "foto",
    "gambar", "orang", "wanita", "pria", "perempuan", "laki", "gadis",
    "anak", "posisi", "ekspresi", "komposisi", "tidak", "bukan", "ini",
    "itu", "tersebut", "tubuh", "pakaiannya", "bajunya", "gaunnya",
    "latarnya", "rambutnya", "wajahnya", "warnanya", "semuanya",
}

_SYSTEM_PROMPT = (
    "You are an expert translator for FLUX.1 Kontext image-editing prompts. "
    "Translate the user's editing instruction into clear, natural, precise English. "
    "Preserve all preservation constraints (e.g. keeping background, face, hair, pose, lighting unchanged). "
    "Do not invent or add unrequested objects, styles, or scenery. "
    "If the prompt is already entirely in English, return it verbatim. "
    "Output ONLY the final English prompt without quotes, labels, or explanation."
)


class OllamaService:
    """Translates non-English editing prompts to English via Ollama."""

    def __init__(self, ollama_url: str, model: str):
        self.ollama_url = ollama_url
        self.model = model

    def needs_translation(self, prompt: str) -> bool:
        """Return True if the prompt contains non-ASCII or Indonesian/Malay words."""
        if not prompt or not prompt.strip():
            return False
        if any(ord(ch) > 127 for ch in prompt):
            return True
        tokens = set(re.findall(r"[a-zA-Z]+", prompt.lower()))
        return bool(tokens & _INDONESIAN_MARKERS)

    async def translate_to_english(self, prompt: str) -> str:
        """Translate an image editing prompt to English using Ollama qwen2.5:7b."""
        clean = prompt.strip()
        async with httpx.AsyncClient(timeout=120.0) as client:
            res = await client.post(
                f"{self.ollama_url}/api/generate",
                json={
                    "model": self.model,
                    "system": _SYSTEM_PROMPT,
                    "prompt": clean,
                    "stream": False,
                    "keep_alive": 0,
                    "options": {"temperature": 0.0},
                },
            )
            res.raise_for_status()
            translated = (res.json().get("response") or "").strip()

        if len(translated) >= 2 and translated[0] == translated[-1] and translated[0] in ('"', "'"):
            translated = translated[1:-1].strip()

        if not translated:
            logging.warning("Ollama returned empty translation; falling back to original prompt.")
            return clean

        logging.info(f"[TRANSLATE] {clean!r} -> {translated!r}")
        return translated
