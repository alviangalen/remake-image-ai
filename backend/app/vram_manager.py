import asyncio
import logging
import httpx

logging.basicConfig(
    filename="/logs/backend.log",
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)


class VRAMGuard:
    """Serializes GPU workloads between Ollama and ComfyUI on 8GB VRAM."""

    def __init__(self, ollama_url: str, comfy_url: str, llm_model: str):
        self.lock = asyncio.Lock()
        self.active_engine = "IDLE"  # IDLE | OLLAMA | COMFY
        self.ollama_url = ollama_url
        self.comfy_url = comfy_url
        self.llm_model = llm_model
        self._ollama_dirty = False

    async def flush_ollama(self):
        """Force Ollama to unload the active LLM from GPU VRAM."""
        logging.info("Mengosongkan VRAM dari Ollama...")
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                res = await client.post(
                    f"{self.ollama_url}/api/generate",
                    json={"model": self.llm_model, "keep_alive": 0},
                )
                res.raise_for_status()
            self._ollama_dirty = False
        except Exception as exc:
            logging.warning(f"Gagal mengosongkan VRAM Ollama: {exc}")

    async def flush_comfy(self):
        """Force ComfyUI to unload models and free CUDA memory."""
        logging.info("Mengosongkan VRAM dari ComfyUI...")
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                res = await client.post(
                    f"{self.comfy_url}/free",
                    json={"unload_models": True, "free_memory": True},
                )
                res.raise_for_status()
        except Exception as exc:
            logging.warning(f"Gagal mengosongkan VRAM ComfyUI: {exc}")

    async def switch_to(self, target: str):
        """Flush the opposing engine before switching GPU ownership."""
        if target == "COMFY":
            if self.active_engine == "OLLAMA" or self._ollama_dirty:
                await self.flush_ollama()
        elif target == "OLLAMA":
            if self.active_engine == "COMFY":
                await self.flush_comfy()
            self._ollama_dirty = True

        if self.active_engine != target:
            self.active_engine = target
            logging.info(f"VRAM RTX 4060 dialihkan ke: {target}")
