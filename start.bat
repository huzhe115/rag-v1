@echo off
rem RAG-v1 one-click start: backend serves frontend/dist, browser opens automatically
cd /d "%~dp0backend"
start "RAG-v1 backend" /min cmd /c "..\.venv\Scripts\python -m uvicorn main:app --host 127.0.0.1 --port 8000"
timeout /t 10 /nobreak >nul
start "" http://127.0.0.1:8000
