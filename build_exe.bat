@echo off
rem ============================================================
rem  CORS Local Proxy - one-click EXE build script (Windows)
rem  Output: dist\CORS-Local-Proxy.exe
rem  Requirement: Python 3.9 - 3.13 from https://www.python.org
rem  (install with "Add python.exe to PATH" checked)
rem ============================================================
setlocal
cd /d "%~dp0"

echo.
echo [1/4] Checking Python ...
where python >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Python not found. Please install Python 3.9+ from
    echo         https://www.python.org/downloads/  ^(check "Add python.exe to PATH"^)
    echo         Then re-run this script.
    pause
    exit /b 1
)
python --version

echo.
echo [2/4] Installing dependencies ^(requests + pyinstaller^) ...
python -m pip install --upgrade pip -q
python -m pip install -r requirements.txt -q
if errorlevel 1 (
    echo [ERROR] pip install failed. Check your network or pip mirror, then retry.
    pause
    exit /b 1
)

echo.
echo [3/4] Building EXE with PyInstaller ^(takes 1-3 minutes^) ...
python -m PyInstaller --noconfirm --clean --onefile --windowed ^
    --icon "icon.ico" --add-data "icon.ico;." ^
    --name "CORS-Local-Proxy" main.py
if errorlevel 1 (
    echo [ERROR] Build failed. Scroll up to read the error message.
    pause
    exit /b 1
)

echo.
echo [4/4] Done!
echo ================================================
echo   Output:  %~dp0dist\CORS-Local-Proxy.exe
echo   Double-click it to run. No Python needed at runtime.
echo ================================================
echo.
choice /C YN /M "Open the output folder now"
if errorlevel 2 goto end
explorer "%~dp0dist"
:end
pause
