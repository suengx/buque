.PHONY: db-up db-down backend-install frontend-install init-db api pipeline pipeline-erp frontend test dev stop

db-up:
	docker compose up -d

db-down:
	docker compose down

stop: db-down
	@echo "PostgreSQL 已停止。若 API/前端仍在运行，请在对应终端 Ctrl+C。"

backend-install:
	cd backend && uv sync --extra dev

frontend-install:
	cd frontend && npm install

init-db: db-up
	@echo "Waiting for postgres..."
	@sleep 3
	cd backend && uv run python scripts/init_db.py

api:
	cd backend && uv run buque-api

pipeline:
	cd backend && uv run buque-job

pipeline-erp:
	cd backend && BUQUE_USE_ERP=1 uv run buque-job

frontend:
	cd frontend && npm run dev

# 一键开发：PostgreSQL + API + 前端（Ctrl+C 停止 API 与前端）
dev: db-up
	@echo "补雀 BuQue 开发环境"
	@echo "  API:      http://localhost:8000"
	@echo "  Frontend: http://localhost:3000"
	@echo "  首次启动请先执行: make init-db"
	@$(MAKE) -j2 api frontend

test:
	cd backend && uv run pytest -q
