# GPS ATLAS -- single container, single process.
# Stage 1: build the React frontend into static files.
# Stage 2: run the FastAPI backend, which serves those static files itself
# (see backend/app/main.py's StaticFiles mount), so only ONE process/port
# is needed -- exactly what Render's free web-service tier expects.

FROM node:22-bookworm AS frontend-build
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm install
COPY frontend/ ./
RUN npm run build

FROM python:3.11-slim AS runtime
WORKDIR /app

# tesseract-ocr: needed for OCR of scanned images/PDFs (pytesseract).
# Kept minimal on purpose -- LibreOffice (legacy .doc/.xls/.ppt conversion)
# is intentionally NOT installed here: it's a large image (~600MB extra) and
# the app already degrades gracefully (a clear error, not a crash) for those
# few legacy formats when it's absent. Add `libreoffice` to the apt list
# below if you need that path for a demo.
RUN apt-get update \
    && apt-get install -y --no-install-recommends tesseract-ocr \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

COPY backend/ ./backend/
COPY --from=frontend-build /app/frontend/dist ./frontend/dist

# Render (and most PaaS) inject the port to bind to via $PORT at runtime --
# never hard-code 8000 in the CMD, or the platform's health check can never
# reach the app.
ENV ATLAS_ENVIRONMENT=production
ENV PYTHONUNBUFFERED=1
EXPOSE 8000

WORKDIR /app/backend
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
