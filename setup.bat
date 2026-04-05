@echo off
REM ╔══════════════════════════════════════════════╗
REM ║  SETUP SCRIPT (Windows) - YouTube Clipper    ║
REM ╚══════════════════════════════════════════════╝

echo Installing dependencies...

REM Check Python
where python >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo Python tidak ditemukan. Install Python 3.8+ dari python.org
    pause
    exit /b 1
)

REM Check FFmpeg
where ffmpeg >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo FFmpeg tidak ditemukan.
    echo Download dari https://ffmpeg.org atau install: choco install ffmpeg
    pause
    exit /b 1
)

REM Create venv
echo Creating virtual environment...
python -m venv venv
call venv\Scripts\activate.bat

REM Install
echo Installing Python packages...
pip install --upgrade pip
pip install -r requirements.txt

echo.
echo Setup selesai!
echo.
echo LANGKAH SELANJUTNYA:
echo   1. Edit config.py - isi API key
echo   2. Aktifkan venv: venv\Scripts\activate.bat
echo   3. Jalankan: python clipper.py ^<youtube_url^>
echo.
pause
