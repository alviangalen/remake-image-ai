import asyncio
import inspect
import io
import json
import logging
import random
import time
import urllib.parse
import uuid
from typing import Any, Callable, Optional

import httpx
import websockets

try:
    from PIL import Image, ImageOps
except ImportError:  # pragma: no cover - fallback before backend image rebuild
    Image = None
    ImageOps = None

_NODE_STAGE_MAP = {
    "10": ("preparing", 12, "Memuat gambar referensi..."),
    "42": ("preparing", 13, "Menyesuaikan resolusi FLUX.1 Kontext..."),
    "44": ("preparing", 14, "Membaca dimensi target..."),
    "43": ("preparing", 14, "Menyiapkan kanvas latent..."),
    "11": ("loading_models", 16, "Memuat Text Encoder (CLIP & T5)..."),
    "6": ("conditioning", 18, "Menyandikan prompt teks..."),
    "40": ("conditioning", 18, "Menyiapkan negative conditioning..."),
    "12": ("loading_models", 19, "Memuat VAE..."),
    "16": ("conditioning", 20, "Menyandikan gambar referensi ke latent..."),
    "41": ("conditioning", 21, "Mengaitkan ReferenceLatent..."),
    "35": ("conditioning", 22, "Menerapkan FluxGuidance..."),
    "13": ("loading_models", 22, "Memuat model FLUX.1 Kontext GGUF..."),
    "17": ("sampling", 23, "Memulai sampling difusi..."),
    "8": ("decoding", 96, "Mendekode hasil dari latent (VAE Decode)..."),
    "9": ("saving", 98, "Menyimpan gambar output..."),
}


async def _emit(cb: Optional[Callable[[dict], Any]], payload: dict) -> None:
    if cb is None:
        return
    res = cb(payload)
    if inspect.isawaitable(res):
        await res


class ComfyService:
    """Client orchestrator for ComfyUI FLUX.1 Kontext image editing."""

    def __init__(self, comfy_url: str, workflow_path: str = "/app/flux_edit.json"):
        self.http_url = comfy_url.rstrip("/")
        self.ws_url = self.http_url.replace("https://", "wss://").replace("http://", "ws://")
        self.workflow_path = workflow_path

    def _prepare_png_bytes(self, image_bytes: bytes) -> bytes:
        """Normalize input image orientation, color space (RGB), and format (PNG)."""
        if Image is None or ImageOps is None:
            return image_bytes

        with Image.open(io.BytesIO(image_bytes)) as img:
            img = ImageOps.exif_transpose(img)
            if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
                rgba = img.convert("RGBA")
                background = Image.new("RGB", rgba.size, (255, 255, 255))
                background.paste(rgba, mask=rgba.split()[3])
                rgb = background
            elif img.mode != "RGB":
                rgb = img.convert("RGB")
            else:
                rgb = img

            out = io.BytesIO()
            rgb.save(out, format="PNG")
            return out.getvalue()

    def _extract_output_image(self, outputs: dict) -> dict:
        """Select the SaveImage output entry from ComfyUI history outputs."""
        preferred = outputs.get("9", {}).get("images", [])
        for img_info in preferred:
            if img_info.get("type", "output") == "output":
                return img_info

        for node_id in outputs:
            for img_info in outputs[node_id].get("images", []):
                if img_info.get("type", "output") == "output":
                    return img_info

        for node_id in outputs:
            images = outputs[node_id].get("images", [])
            if images:
                return images[0]

        raise RuntimeError("Tidak ada output gambar dari ComfyUI")

    async def process_image_with_meta(
        self,
        image_bytes: bytes,
        filename: str,
        prompt: str,
        denoise: float = 1.0,
        guidance: float = 2.5,
        steps: int = 20,
        seed: Optional[int] = None,
        on_progress: Optional[Callable[[dict], Any]] = None,
    ) -> tuple[bytes, dict]:
        """Upload image, execute FLUX.1 Kontext workflow, and return (png_bytes, metadata)."""
        started = time.monotonic()
        client_id = str(uuid.uuid4())
        unique_filename = f"victus_{client_id}.png"
        clean_bytes = self._prepare_png_bytes(image_bytes)

        actual_seed = int(seed) if seed is not None else random.randint(1, 999_999_999)
        actual_denoise = max(0.0, min(1.0, float(denoise)))
        actual_guidance = float(guidance)
        actual_steps = max(1, int(steps))

        await _emit(on_progress, {
            "stage": "uploading",
            "progress": 10,
            "step": 0,
            "total_steps": actual_steps,
            "eta_seconds": None,
            "message": "Mengunggah gambar & workflow ke ComfyUI...",
        })

        async with httpx.AsyncClient(timeout=600.0) as client:
            files = {
                "image": (unique_filename, clean_bytes, "image/png"),
                "overwrite": (None, "true"),
            }
            up_res = await client.post(f"{self.http_url}/upload/image", files=files)
            up_res.raise_for_status()
            up_data = up_res.json()
            uploaded_name = up_data["name"]
            subfolder = up_data.get("subfolder", "")
            uploaded_ref = f"{subfolder}/{uploaded_name}" if subfolder else uploaded_name

            with open(self.workflow_path, "r", encoding="utf-8") as f:
                workflow = json.load(f)

            workflow["10"]["inputs"]["image"] = uploaded_ref
            workflow["6"]["inputs"]["text"] = prompt
            workflow["17"]["inputs"]["seed"] = actual_seed
            workflow["17"]["inputs"]["steps"] = actual_steps
            workflow["17"]["inputs"]["denoise"] = actual_denoise
            workflow["35"]["inputs"]["guidance"] = actual_guidance

            # EmptySD3LatentImage (all zeros) is only valid at denoise == 1.0.
            # If partial denoise < 1.0 is explicitly requested, start from VAEEncode ("16").
            if actual_denoise < 1.0:
                workflow["17"]["inputs"]["latent_image"] = ["16", 0]
            else:
                workflow["17"]["inputs"]["latent_image"] = ["43", 0]

            logging.info(
                "[EDIT] client_id=%s image=%r seed=%s steps=%s denoise=%.2f guidance=%.2f prompt=%r",
                client_id,
                uploaded_ref,
                actual_seed,
                actual_steps,
                actual_denoise,
                actual_guidance,
                prompt,
            )

            ws_endpoint = f"{self.ws_url}/ws?clientId={client_id}"
            sampling_started_at: Optional[float] = None
            first_step_at: Optional[float] = None

            async with websockets.connect(
                ws_endpoint, max_size=None, ping_interval=20, ping_timeout=60
            ) as ws:
                q_res = await client.post(
                    f"{self.http_url}/prompt",
                    json={"prompt": workflow, "client_id": client_id},
                )
                if q_res.status_code >= 400:
                    raise RuntimeError(
                        f"ComfyUI rejected workflow ({q_res.status_code}): {q_res.text}"
                    )
                prompt_id = q_res.json()["prompt_id"]

                try:
                    while True:
                        raw_msg = await asyncio.wait_for(ws.recv(), timeout=600.0)
                        if not isinstance(raw_msg, str):
                            continue
                        data = json.loads(raw_msg)
                        msg_type = data.get("type")
                        msg_data = data.get("data", {})
                        if msg_data.get("prompt_id") != prompt_id:
                            continue

                        if msg_type == "execution_error":
                            raise RuntimeError(
                                f"ComfyUI error at node {msg_data.get('node_type')} "
                                f"({msg_data.get('node_id')}): {msg_data.get('exception_message')}"
                            )
                        if msg_type == "execution_interrupted":
                            raise RuntimeError("ComfyUI execution interrupted")
                        if msg_type == "execution_success":
                            break
                        if msg_type == "executing":
                            node_id = msg_data.get("node")
                            if node_id is None:
                                break
                            node_key = str(node_id)
                            if node_key == "17" and sampling_started_at is None:
                                sampling_started_at = time.monotonic()
                            if node_key in _NODE_STAGE_MAP:
                                st, pct, label = _NODE_STAGE_MAP[node_key]
                                await _emit(on_progress, {
                                    "stage": st,
                                    "progress": pct,
                                    "step": 0,
                                    "total_steps": actual_steps,
                                    "eta_seconds": None,
                                    "message": label,
                                })
                        elif msg_type == "progress":
                            val = int(msg_data.get("value", 0))
                            mx = max(1, int(msg_data.get("max", actual_steps)))
                            now = time.monotonic()
                            if val >= 1 and first_step_at is None:
                                first_step_at = now
                            pct = min(95, 23 + round((val / mx) * 72))
                            eta_sec: Optional[int] = None
                            if val >= 1 and sampling_started_at is not None:
                                elapsed_sampling = now - sampling_started_at
                                sec_per_step = elapsed_sampling / val
                                eta_sec = max(1, round(sec_per_step * (mx - val) + 4))
                            await _emit(on_progress, {
                                "stage": "sampling",
                                "progress": pct,
                                "step": val,
                                "total_steps": mx,
                                "eta_seconds": eta_sec,
                                "message": f"Memproses difusi FLUX.1 Kontext ({val}/{mx} langkah)...",
                            })
                except websockets.ConnectionClosed:
                    logging.warning("WebSocket closed early for prompt_id=%s; checking /history", prompt_id)

            await _emit(on_progress, {
                "stage": "downloading",
                "progress": 99,
                "step": actual_steps,
                "total_steps": actual_steps,
                "eta_seconds": 1,
                "message": "Mengambil gambar hasil...",
            })

            hist_entry = None
            for _ in range(10):
                hist_res = await client.get(f"{self.http_url}/history/{prompt_id}")
                hist_res.raise_for_status()
                hist_json = hist_res.json()
                if prompt_id in hist_json:
                    hist_entry = hist_json[prompt_id]
                    break
                await asyncio.sleep(0.5)

            if not hist_entry:
                raise RuntimeError(f"ComfyUI history missing for prompt_id={prompt_id}")

            status_info = hist_entry.get("status", {})
            if status_info.get("status_str") == "error":
                raise RuntimeError(f"ComfyUI execution failed: {status_info}")

            outputs = hist_entry.get("outputs", {})
            img_info = self._extract_output_image(outputs)
            params = urllib.parse.urlencode({
                "filename": img_info["filename"],
                "subfolder": img_info.get("subfolder", ""),
                "type": img_info.get("type", "output"),
            })
            img_res = await client.get(f"{self.http_url}/view?{params}")
            img_res.raise_for_status()

            elapsed = round(time.monotonic() - started, 2)
            meta = {
                "prompt_id": prompt_id,
                "seed": actual_seed,
                "steps": actual_steps,
                "denoise": actual_denoise,
                "guidance": actual_guidance,
                "prompt": prompt,
                "elapsed_seconds": elapsed,
                "output_filename": img_info["filename"],
            }
            return img_res.content, meta

    async def process_image(
        self,
        image_bytes: bytes,
        filename: str,
        prompt: str,
        denoise: float = 1.0,
        guidance: float = 2.5,
        steps: int = 20,
        seed: Optional[int] = None,
    ) -> bytes:
        """Backward-compatible wrapper returning only output PNG bytes."""
        img_bytes, _ = await self.process_image_with_meta(
            image_bytes=image_bytes,
            filename=filename,
            prompt=prompt,
            denoise=denoise,
            guidance=guidance,
            steps=steps,
            seed=seed,
        )
        return img_bytes
