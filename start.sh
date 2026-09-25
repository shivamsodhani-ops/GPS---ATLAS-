#!/usr/bin/env bash
# One-command launcher for GPS ATLAS: builds the frontend once, installs
# backend dependencies once, then runs everything as a single process on
# http://localhost:8000. Safe to re-run -- it skips steps that are already done.
set -euo pipefail
cd "$(dirname "$0")"

echo "== GPS ATLAS setup =="

if [ ! -d "backend/.venv" ]; then
  echo "-- creating Python virtual environment"
  python3 -m venv backend/.venv
fi
# shellcheck disable=SC1091
source backend/.venv/bin/activate

echo "-- installing backend dependencies (first run only takes a minute)"
pip install --quiet --upgrade pip
pip install --quiet -r backend/requirements.txt

if [ ! -d "frontend/dist" ]; then
  echo "-- building the web app (first run only)"
  if [ ! -d "frontend/node_modules" ]; then
    (cd frontend && npm install --silent)
  fi
  (cd frontend && npm run build --silent)
fi

echo ""
echo "== Starting GPS ATLAS on http://localhost:8000 =="
echo "   Default admin login: admin@gpsrenewables.com / ChangeMe!2026"
echo "   (you will be forced to change this password on first login)"
echo ""

cd backend
exec python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000
