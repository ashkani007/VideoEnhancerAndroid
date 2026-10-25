@echo off
REM Great History Makers local worker: polls the job branch every 60 s while this window is open (Ctrl+C stops it).
REM Nothing is scheduled; close the window and no jobs run.
set COMFY=C:\AI\ComfyUI_windows_portable
set REPO=C:\AI\ghm-worker\VideoEnhancerAndroid
"%COMFY%\python_embeded\python.exe" "%REPO%\great_history_makers\comfyui\worker\ghm_worker.py" --repo "%REPO%" %*
pause
