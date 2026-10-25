@echo off
REM Checks ComfyUI, the GPU (VRAM) and the required models/nodes. ComfyUI must be running.
set COMFY=C:\AI\ComfyUI_windows_portable
set REPO=C:\AI\ghm-worker\VideoEnhancerAndroid
nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv
"%COMFY%\python_embeded\python.exe" "%REPO%\great_history_makers\comfyui\worker\ghm_worker.py" --check
pause
