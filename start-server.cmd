@echo off
rem Double-click to start Stream Anything Server with config.toml from this folder.
rem First-time setup is in README.md (create the virtual environment, then copy config.example.toml).
cd /d "%~dp0"
if not exist ".venv\Scripts\stream-anything-server.exe" (
    echo Not installed yet. See "Installation" in README.md.
    pause
    exit /b 1
)
".venv\Scripts\stream-anything-server.exe" --config config.toml
pause
