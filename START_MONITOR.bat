@echo off
cd /d "%~dp0"
echo Starting AUTONOMI AGENTIC ILMIAH monitor...
echo.
echo Browser will open this address:
echo http://127.0.0.1:8000
echo.
start "" "http://127.0.0.1:8000"
python -m src monitor --port 8000
pause
