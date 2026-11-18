import os
import httpx
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from vram_manager import VRAMGuard, logging
from services.comfy_svc import ComfyService

app = FastAPI(title="Victus AI Studio Orchestrator")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://ollama:11434")
COMFY_URL = os.getenv("COMFY_URL", "http://comfyui:8188")
LLM_MODEL = os.getenv("LLM_MODEL", "qwen2.5:7b")

guard = VRAMGuard(ollama_url=OLLAMA_URL, comfy_url=COMFY_URL, llm_model=LLM_MODEL)
comfy_service = ComfyService(comfy_url=COMFY_URL)

@app.get("/api/health")
async def health_check():
    status = {"active_vram_owner": guard.active_engine, "ollama": False, "comfyui": False}
    async with httpx.AsyncClient(timeout=3.0) as client:
        try:
            r1 = await client.get(f"{guard.ollama_url}/api/tags")
            status["ollama"] = (r1.status_code == 200)
        except Exception:
            pass
        try:
            r2 = await client.get(f"{guard.comfy_url}/system_stats")
            status["comfyui"] = (r2.status_code == 200)
        except Exception:
            pass
    return status

@app.post("/api/chat")
async def chat_llm(prompt: str = Form(...)):
    async with guard.lock:
        try:
            await guard.switch_to("OLLAMA")
            async with httpx.AsyncClient(timeout=120.0) as client:
                res = await client.post(f"{guard.ollama_url}/api/generate", json={
                    "model": guard.llm_model,
                    "prompt": prompt,
                    "stream": False,
                    "keep_alive": 0
                })
                res.raise_for_status()
                return res.json()
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
        finally:
            guard.active_engine = "IDLE"

@app.post("/api/edit-image")
async def edit_image(
    prompt: str = Form(...),
    denoise: float = Form(0.65),
    image: UploadFile = File(...)
):
    async with guard.lock:
        try:
            await guard.switch_to("COMFY")
            img_bytes = await image.read()
            result_bytes = await comfy_service.process_image(
                image_bytes=img_bytes,
                filename=image.filename,
                prompt=prompt,
                denoise=denoise
            )
            return Response(content=result_bytes, media_type="image/png")
        except Exception as e:
            logging.error(f"Error edit-image: {e}")
            raise HTTPException(status_code=500, detail=str(e))
        finally:
            await guard.flush_comfy()
            guard.active_engine = "IDLE"

@app.post("/api/flush")
async def manual_flush():
    await guard.flush_ollama()
    await guard.flush_comfy()
    guard.active_engine = "IDLE"
    return {"status": "flushed"}
