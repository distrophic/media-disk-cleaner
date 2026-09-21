@echo off
setlocal EnableExtensions
cd /d "%~dp0"

if not exist ".venv\Scripts\activate.bat" (
    echo ERROR: virtualenv .venv not found. Create it and install requirements.txt
    exit /b 1
)
call ".venv\Scripts\activate.bat"

python -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 12) else 1)"
if errorlevel 1 (
    echo ERROR: Python 3.12 or newer is required.
    exit /b 1
)

python -c "import PyInstaller" 1>nul 2>nul
if errorlevel 1 (
    echo Installing build dependencies...
    python -m pip install -r requirements-build.txt
    if errorlevel 1 exit /b 1
)

python -m pip install -r requirements.txt
if errorlevel 1 exit /b 1

echo Running tests...
python -m pytest tests -v
if errorlevel 1 (
    echo ERROR: tests failed. EXE build stopped.
    exit /b 1
)

if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

echo Building one-file EXE with MediaDiskCleaner-onefile.spec...
python -m PyInstaller --noconfirm --clean MediaDiskCleaner-onefile.spec
if errorlevel 1 (
    echo ERROR: PyInstaller failed.
    exit /b 1
)

if not exist "dist\MediaDiskCleaner.exe" (
    echo ERROR: dist\MediaDiskCleaner.exe was not created.
    exit /b 1
)

echo.
echo Build OK. One file, no extra folders to copy.
echo EXE: %CD%\dist\MediaDiskCleaner.exe
echo Logs and reports stay in %%LOCALAPPDATA%%\MediaDiskCleaner\
endlocal
exit /b 0
