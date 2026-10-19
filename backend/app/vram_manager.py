import asyncio
import httpx
import logging

logging.basicConfig(filename="/logs/backend.log", level=logging.INFO, 
                    format="%(asctime)s [%(levelname)s] %(message)s")

class VRAMGuard:
    def __init__(self, ollama_url: str, comfy_url: str, llm_model: str):
        self.lock = asyncio.Lock()
        self.active_engine = "IDLE" # IDLE | OLLAMA | COMFY
        self.ollama_url = ollama_url
        self.comfy_url = comfy_url
        self.llm_model = llm_model

    async def flush_ollama(self):
        """Paksa Ollama buang model dari VRAM 4060"""
        logging.info("Mengosongkan VRAM dari Ollama...")
        async with httpx.AsyncClient() as client:
            await client.post(f"{self.ollama_url}/api/generate", 
                              json={"model": self.llm_model, "keep_alive": 0})

    async def flush_comfy(self):
        """Paksa ComfyUI unload model gambar dari VRAM 4060"""
        logging.info("Mengosongkan VRAM dari ComfyUI...")
        async with httpx.AsyncClient() as client:
            await client.post(f"{self.comfy_url}/free", 
                              json={"unload_models": True, "free_memory": True})

    async def switch_to(self, target: str):
        """Otomatis bersihkan VRAM lawan sebelum nyalakan engine tujuan"""
        if self.active_engine != target:
            if self.active_engine == "OLLAMA":
                await self.flush_ollama()
            elif self.active_engine == "COMFY":
                await self.flush_comfy()
            self.active_engine = target
            logging.info(f"VRAM RTX 4060 dialihkan ke: {target}")