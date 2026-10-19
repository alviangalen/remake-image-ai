import json
import uuid
import urllib.parse
import httpx
import websockets

class ComfyService:
    def __init__(self, comfy_url: str, workflow_path: str = "/app/workflows/flux_edit.json"):
        self.http_url = comfy_url
        self.ws_url = comfy_url.replace("http://", "ws://")
        self.workflow_path = workflow_path

    async def process_image(self, image_bytes: bytes, filename: str, prompt: str, denoise: float) -> bytes:
        client_id = str(uuid.uuid4())

        async with httpx.AsyncClient(timeout=300.0) as client:
            # 1. Upload foto asli dari React ke ComfyUI
            files = {"image": (filename, image_bytes, "image/png"), "overwrite": (None, "true")}
            up_res = await client.post(f"{self.http_url}/upload/image", files=files)
            up_res.raise_for_status()
            uploaded_name = up_res.json()["name"]

            # 2. Muat template workflow JSON & suntikkan parameter dari UI React
            with open(self.workflow_path, "r") as f:
                workflow = json.load(f)

            workflow["10"]["inputs"]["image"] = uploaded_name       # Node LoadImage
            workflow["6"]["inputs"]["text"] = prompt                # Node Prompt Positif
            workflow["17"]["inputs"]["denoise"] = float(denoise)    # Node KSampler Denoise

            # 3. Kirim antrean render ke ComfyUI
            q_res = await client.post(
                f"{self.http_url}/prompt",
                json={"prompt": workflow, "client_id": client_id}
            )
            q_res.raise_for_status()
            prompt_id = q_res.json()["prompt_id"]

            # 4. Pantau WebSocket sampai RTX 4060 selesai merender
            async with websockets.connect(f"{self.ws_url}/ws?clientId={client_id}") as ws:
                async for msg in ws:
                    if isinstance(msg, str):
                        data = json.loads(msg)
                        if data.get("type") == "executing":
                            exec_data = data.get("data", {})
                            if exec_data.get("node") is None and exec_data.get("prompt_id") == prompt_id:
                                break

            # 5. Ambil gambar hasil edit dari ComfyUI dan kirim balik ke React
            hist_res = await client.get(f"{self.http_url}/history/{prompt_id}")
            outputs = hist_res.json()[prompt_id]["outputs"]
            
            for node_id in outputs:
                if "images" in outputs[node_id]:
                    img_info = outputs[node_id]["images"][0]
                    params = urllib.parse.urlencode(img_info)
                    img_res = await client.get(f"{self.http_url}/view?{params}")
                    return img_res.content

            raise RuntimeError("Tidak ada output gambar dari ComfyUI")