# Jalankan semua sistem di background
up:
	docker compose up -d --build

# Matikan semua sistem & kosongkan VRAM
down:
	docker compose down

# [TROUBLESHOOT 1] Cek kondisi semua mesin & penggunaan VRAM RTX 4060
status:
	@echo "=== STATUS CONTAINER ==="
	@docker compose ps
	@echo "\n=== STATUS KESEHATAN ENGINE & GPU ==="
	@curl -s http://localhost:8000/api/health | python3 -m json.tool
	@echo "\n=== PENGGUNAAN VRAM SAAT INI ==="
	@nvidia-smi --query-gpu=name,memory.used,memory.total,utilization.gpu,temperature.gpu --format=csv

# [TROUBLESHOOT 2] Pantau log error secara live
logs:
	docker compose logs -f --tail=50

# [TROUBLESHOOT 3] Paksa kuras VRAM kalau ada proses nyangkut
flush:
	curl -X POST http://localhost:8188/free -H "Content-Type: application/json" -d '{"unload_models": true, "free_memory": true}'
	docker restart victus_ollama

# [HEMAT SSD 120GB] Bersihkan sampah cache build Docker tanpa menghapus model AI
clean-disk:
	docker system prune -f
	docker builder prune -f
	@df -h /