import os
import httpx
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from vram_manager import VRAMGuard, logging
from fastapi.responses import Response
from services.comfy_svc import ComfyService

comfy_service = ComfyService(comfy_url=os.getenv("COMFY_URL", "http://comfyui:8188"))

app = FastAPI(title="AI Studio Orchestrator")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

guard = VRAMGuard(
    ollama_url=os.getenv("OLLAMA_URL", "http://ollama:11434"),
    comfy_url=os.getenv("COMFY_URL", "http://comfyui:8188"),
    llm_model=os.getenv("LLM_MODEL", "qwen2.5:7b")
)

@app.get("/api/health")
async def health_check():
    """Endpoint buat ngecek kondisi semua mesin dari Frontend"""
    status = {"active_vram_owner": guard.active_engine, "ollama": False, "comfyui": False}
    async with httpx.AsyncClient(timeout=3.0) as client:
        try:
            r1 = await client.get(f"{guard.ollama_url}/api/tags")
            status["ollama"] = (r1.status_code == 200)
        except Exception as e:
            logging.error(f"Ollama Down: {e}")
        try:
            r2 = await client.get(f"{guard.comfy_url}/system_stats")
            status["comfyui"] = (r2.status_code == 200)
            if status["comfyui"]:
                status["gpu_stats"] = r2.json().get("devices", [])
        except Exception as e:
            logging.error(f"ComfyUI Down: {e}")
    return status

@app.post("/api/chat")
async def chat_llm(prompt: str = Form(...)):
    async with guard.lock:
        await guard.switch_to("OLLAMA")
        async with httpx.AsyncClient(timeout=120.0) as client:
            res = await client.post(f"{guard.ollama_url}/api/generate", json={
                "model": guard.llm_model,
                "prompt": prompt,
                "stream": False,
                "keep_alive": 0 # Beres jawab langsung kosongkan VRAM!
            })
            guard.active_engine = "IDLE"
            return res.json()

@app.post("/api/edit-image")
async def edit_image(
    prompt: str = Form(...),
    denoise: float = Form(0.60),
    image: UploadFile = File(...)
):
    async with guard.lock:
        try:
            # 1. Alihkan 100% VRAM RTX 4060 ke ComfyUI
            await guard.switch_to("COMFY")
            img_bytes = await image.read()

            # 2. Eksekusi edit gambar
            result_bytes = await comfy_service.process_image(
                image_bytes=img_bytes,
                filename=image.filename,
                prompt=prompt,
                denoise=denoise
            )
            return Response(content=result_bytes, media_type="image/png")
        finally:
            # 3. Wajib kuras VRAM setelah selesai (bahkan jika error sekalipun!)
            await guard.flush_comfy()
            guard.active_engine = "IDLE"

@app.post("/api/flush")
async def manual_flush():
    await guard.flush_ollama()
    await guard.flush_comfy()
    guard.active_engine = "IDLE"
    return {"status": "flushed"}