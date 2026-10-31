#!/usr/bin/env bash
set -e
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"
[ -d backend/.venv ] || python3 -m venv backend/.venv
source backend/.venv/bin/activate
pip install -r backend/requirements.txt
(cd frontend && npm install && npm run dev) &
FRONT_PID=$!
(cd backend && exec ../backend/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8765) &
BACK_PID=$!
trap 'kill $FRONT_PID $BACK_PID 2>/dev/null || true' EXIT INT TERM
wait
