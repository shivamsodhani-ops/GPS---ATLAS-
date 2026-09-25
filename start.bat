@echo off
REM One-command launcher for GPS ATLAS on Windows.
cd /d "%~dp0"

echo == GPS ATLAS setup ==

if not exist backend\.venv (
  echo -- creating Python virtual environment
  python -m venv backend\.venv
)
call backend\.venv\Scripts\activate.bat

echo -- installing backend dependencies (first run only takes a minute)
pip install --quiet --upgrade pip
pip install --quiet -r backend\requirements.txt

if not exist frontend\dist (
  echo -- building the web app (first run only)
  if not exist frontend\node_modules (
    cd frontend
    call npm install --silent
    cd ..
  )
  cd frontend
  call npm run build --silent
  cd ..
)

echo.
echo == Starting GPS ATLAS on http://localhost:8000 ==
echo    Default admin login: admin@gpsrenewables.com / ChangeMe!2026
echo    (you will be forced to change this password on first login)
echo.

cd backend
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
