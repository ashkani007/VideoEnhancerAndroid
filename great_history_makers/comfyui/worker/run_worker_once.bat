@echo off
REM Great History Makers: process the job queue ONCE, then exit (no polling, nothing scheduled).
set COMFY=C:\AI\ComfyUI_windows_portable
set REPO=C:\AI\ghm-worker\VideoEnhancerAndroid
"%COMFY%\python_embeded\python.exe" "%REPO%\great_history_makers\comfyui\worker\ghm_worker.py" --repo "%REPO%" --once
pause
