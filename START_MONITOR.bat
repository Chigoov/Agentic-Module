@echo off
cd /d "%~dp0"
echo Starting AUTONOMI AGENTIC ILMIAH monitor...
echo.
echo Open this address in your browser:
echo http://127.0.0.1:8000
echo.
python -m src monitor --port 8000
pause
