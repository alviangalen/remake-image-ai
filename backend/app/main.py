import asyncio
import os
import time
import uuid
from typing import Optional
import httpx
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from vram_manager import VRAMGuard, logging
from services.comfy_svc import ComfyService
from services.ollama_svc import OllamaService

app = FastAPI(title="Victus AI Studio Orchestrator")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Seed", "X-Guidance", "X-Denoise", "X-Steps", "X-Prompt", "X-Elapsed-Seconds"],
)

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://ollama:11434")
COMFY_URL = os.getenv("COMFY_URL", "http://comfyui:8188")
LLM_MODEL = os.getenv("LLM_MODEL", "qwen2.5:7b")

guard = VRAMGuard(ollama_url=OLLAMA_URL, comfy_url=COMFY_URL, llm_model=LLM_MODEL)
comfy_service = ComfyService(comfy_url=COMFY_URL)
ollama_service = OllamaService(ollama_url=OLLAMA_URL, model=LLM_MODEL)

# In-memory store for async edit jobs with bounded retention
_EDIT_JOBS: dict[str, dict] = {}
_JOB_TTL_SECONDS = 1800
_MAX_JOBS = 20


def _prune_old_jobs() -> None:
    now = time.monotonic()
    expired = [
        jid for jid, job in _EDIT_JOBS.items()
        if job["status"] in ("completed", "failed") and (now - job["updated_at"]) > _JOB_TTL_SECONDS
    ]
    for jid in expired:
        _EDIT_JOBS.pop(jid, None)

    if len(_EDIT_JOBS) > _MAX_JOBS:
        finished = sorted(
            ((job["updated_at"], jid) for jid, job in _EDIT_JOBS.items() if job["status"] in ("completed", "failed"))
        )
        for _, jid in finished[: max(0, len(_EDIT_JOBS) - _MAX_JOBS)]:
            _EDIT_JOBS.pop(jid, None)


def _parse_seed(seed: Optional[str]) -> Optional[int]:
    if seed is None or seed.strip() == "":
        return None
    try:
        return int(seed.strip())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Seed harus berupa angka bulat") from exc


def _build_result_headers(meta: dict) -> dict[str, str]:
    safe_prompt_hdr = meta["prompt"][:500].replace("\n", " ").encode("ascii", "replace").decode("ascii")
    return {
        "X-Seed": str(meta["seed"]),
        "X-Guidance": str(meta["guidance"]),
        "X-Denoise": str(meta["denoise"]),
        "X-Steps": str(meta["steps"]),
        "X-Prompt": safe_prompt_hdr,
        "X-Elapsed-Seconds": str(meta["elapsed_seconds"]),
    }


async def _execute_edit_pipeline(
    image_bytes: bytes,
    filename: str,
    prompt: str,
    denoise: float,
    guidance: float,
    steps: int,
    parsed_seed: Optional[int],
    on_progress=None,
) -> tuple[bytes, dict]:
    async with guard.lock:
        try:
            if ollama_service.needs_translation(prompt):
                if on_progress:
                    await on_progress({
                        "stage": "translating",
                        "progress": 5,
                        "step": 0,
                        "total_steps": steps,
                        "eta_seconds": None,
                        "message": "Menerjemahkan instruksi ke Bahasa Inggris (Qwen 2.5)...",
                    })
                await guard.switch_to("OLLAMA")
                english_prompt = await ollama_service.translate_to_english(prompt)
                guard._ollama_dirty = False
            else:
                english_prompt = prompt.strip()

            await guard.switch_to("COMFY")
            return await comfy_service.process_image_with_meta(
                image_bytes=image_bytes,
                filename=filename,
                prompt=english_prompt,
                denoise=denoise,
                guidance=guidance,
                steps=steps,
                seed=parsed_seed,
                on_progress=on_progress,
            )
        finally:
            await guard.flush_comfy()
            guard.active_engine = "IDLE"


async def _run_edit_job(
    job_id: str,
    image_bytes: bytes,
    filename: str,
    prompt: str,
    denoise: float,
    guidance: float,
    steps: int,
    parsed_seed: Optional[int],
) -> None:
    job = _EDIT_JOBS[job_id]

    async def on_progress(update: dict) -> None:
        job.update(update)
        job["status"] = "running"
        job["updated_at"] = time.monotonic()

    try:
        result_bytes, meta = await _execute_edit_pipeline(
            image_bytes=image_bytes,
            filename=filename,
            prompt=prompt,
            denoise=denoise,
            guidance=guidance,
            steps=steps,
            parsed_seed=parsed_seed,
            on_progress=on_progress,
        )
        job.update({
            "status": "completed",
            "stage": "completed",
            "progress": 100,
            "step": meta["steps"],
            "total_steps": meta["steps"],
            "eta_seconds": 0,
            "message": "Selesai!",
            "meta": meta,
            "result_bytes": result_bytes,
            "elapsed_seconds": meta["elapsed_seconds"],
            "updated_at": time.monotonic(),
        })
    except Exception as exc:
        logging.error(f"Error edit job {job_id}: {exc}")
        job.update({
            "status": "failed",
            "stage": "failed",
            "eta_seconds": None,
            "error": str(exc),
            "message": f"Gagal: {exc}",
            "updated_at": time.monotonic(),
        })


@app.get("/api/health")
async def health_check():
    status = {"active_vram_owner": guard.active_engine, "ollama": False, "comfyui": False}
    async with httpx.AsyncClient(timeout=5.0) as client:
        try:
            r1 = await client.get(f"{guard.ollama_url}/api/tags")
            status["ollama"] = r1.status_code == 200
        except Exception as exc:
            logging.warning(f"Ollama health check failed: {exc!r}")
        try:
            r2 = await client.get(f"{guard.comfy_url}/system_stats")
            status["comfyui"] = r2.status_code == 200
        except Exception as exc:
            logging.warning(f"ComfyUI health check failed: {exc!r}")
    return status


@app.post("/api/chat")
async def chat_llm(prompt: str = Form(...)):
    async with guard.lock:
        try:
            await guard.switch_to("OLLAMA")
            async with httpx.AsyncClient(timeout=120.0) as client:
                res = await client.post(
                    f"{guard.ollama_url}/api/generate",
                    json={
                        "model": guard.llm_model,
                        "prompt": prompt,
                        "stream": False,
                        "keep_alive": 0,
                    },
                )
                res.raise_for_status()
                return res.json()
        except Exception as e:
            logging.error(f"Error chat: {e}")
            raise HTTPException(status_code=500, detail=str(e))
        finally:
            await guard.flush_ollama()
            guard.active_engine = "IDLE"


@app.post("/api/edit-image")
async def edit_image(
    prompt: str = Form(...),
    denoise: float = Form(1.0),
    guidance: float = Form(2.5),
    steps: int = Form(20),
    seed: Optional[str] = Form(None),
    image: UploadFile = File(...),
):
    if not prompt.strip():
        raise HTTPException(status_code=400, detail="Prompt tidak boleh kosong")

    parsed_seed = _parse_seed(seed)
    img_bytes = await image.read()
    if not img_bytes:
        raise HTTPException(status_code=400, detail="File gambar kosong")

    try:
        result_bytes, meta = await _execute_edit_pipeline(
            image_bytes=img_bytes,
            filename=image.filename or "input.png",
            prompt=prompt,
            denoise=denoise,
            guidance=guidance,
            steps=steps,
            parsed_seed=parsed_seed,
        )
        return Response(
            content=result_bytes,
            media_type="image/png",
            headers=_build_result_headers(meta),
        )
    except Exception as e:
        logging.error(f"Error edit-image: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/edit-image/jobs")
async def start_edit_job(
    prompt: str = Form(...),
    denoise: float = Form(1.0),
    guidance: float = Form(2.5),
    steps: int = Form(20),
    seed: Optional[str] = Form(None),
    image: UploadFile = File(...),
):
    if not prompt.strip():
        raise HTTPException(status_code=400, detail="Prompt tidak boleh kosong")

    parsed_seed = _parse_seed(seed)
    img_bytes = await image.read()
    if not img_bytes:
        raise HTTPException(status_code=400, detail="File gambar kosong")

    _prune_old_jobs()
    job_id = str(uuid.uuid4())
    now = time.monotonic()
    _EDIT_JOBS[job_id] = {
        "job_id": job_id,
        "status": "queued",
        "stage": "queued",
        "progress": 2,
        "step": 0,
        "total_steps": max(1, int(steps)),
        "eta_seconds": None,
        "message": "Menunggu antrean GPU...",
        "started_at": now,
        "updated_at": now,
        "elapsed_seconds": 0.0,
        "meta": None,
        "result_bytes": None,
        "error": None,
    }
    task = asyncio.create_task(
        _run_edit_job(
            job_id=job_id,
            image_bytes=img_bytes,
            filename=image.filename or "input.png",
            prompt=prompt,
            denoise=denoise,
            guidance=guidance,
            steps=steps,
            parsed_seed=parsed_seed,
        )
    )
    _EDIT_JOBS[job_id]["_task"] = task
    return {"job_id": job_id}


@app.get("/api/edit-image/jobs/{job_id}")
async def get_edit_job_status(job_id: str):
    job = _EDIT_JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job tidak ditemukan")

    elapsed = (
        job["elapsed_seconds"]
        if job["status"] in ("completed", "failed")
        else round(time.monotonic() - job["started_at"], 1)
    )
    meta = job.get("meta") or {}
    return {
        "job_id": job_id,
        "status": job["status"],
        "stage": job["stage"],
        "progress": job["progress"],
        "step": job["step"],
        "total_steps": job["total_steps"],
        "elapsed_seconds": elapsed,
        "eta_seconds": job["eta_seconds"],
        "message": job["message"],
        "seed": meta.get("seed"),
        "prompt": meta.get("prompt"),
        "error": job["error"],
    }


@app.get("/api/edit-image/jobs/{job_id}/result")
async def get_edit_job_result(job_id: str):
    job = _EDIT_JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job tidak ditemukan")
    if job["status"] == "failed":
        raise HTTPException(status_code=500, detail=job["error"] or "Edit gagal")
    if job["status"] != "completed" or job["result_bytes"] is None:
        raise HTTPException(status_code=409, detail="Hasil belum siap")

    return Response(
        content=job["result_bytes"],
        media_type="image/png",
        headers=_build_result_headers(job["meta"]),
    )


@app.post("/api/flush")
async def manual_flush():
    async with guard.lock:
        await guard.flush_ollama()
        await guard.flush_comfy()
        guard.active_engine = "IDLE"
        return {"status": "flushed"}
