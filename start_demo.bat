@echo off
REM Double-click to start the OmniVoice web UI.
cd /d "%~dp0"
title OmniVoice web UI
echo Starting OmniVoice (first run downloads ~3.3 GB of model weights) ...
echo The browser will open at http://127.0.0.1:8001
".venv\Scripts\python.exe" run_local.py demo
pause
