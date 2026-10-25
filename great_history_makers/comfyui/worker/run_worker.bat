@echo off
setlocal
REM Paths come from local_paths.cmd (written by install_ghm_comfyui.ps1, not committed) or from the
REM GHM_COMFYUI_DIR environment variable. Nothing is hardcoded; the worker finds its repository from its own location.
set "HERE=%~dp0"
if exist "%HERE%local_paths.cmd" call "%HERE%local_paths.cmd"
if not defined GHM_COMFYUI_DIR (
  echo GHM_COMFYUI_DIR is not set. Run the installer, or create local_paths.cmd containing:
  echo   set "GHM_COMFYUI_DIR=D:\path\to\ComfyUI_windows_portable"
  pause
  exit /b 1
)
set "PY=%GHM_COMFYUI_DIR%\python_embeded\python.exe"
if not exist "%PY%" (
  echo ComfyUI's Python was not found at "%PY%"
  pause
  exit /b 1
)
REM Polls the job queue every 60 s while this window is open (Ctrl+C stops it). Nothing is scheduled.
"%PY%" -s "%HERE%ghm_worker.py" %*
pause
