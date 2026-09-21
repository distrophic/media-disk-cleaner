@echo off
setlocal EnableExtensions
cd /d "%~dp0"

if exist ".venv\Scripts\activate.bat" (
    call ".venv\Scripts\activate.bat"
)

python -m pytest tests -v
exit /b %ERRORLEVEL%
