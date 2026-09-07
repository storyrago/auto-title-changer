@echo off
chcp 65001 > nul
cd /d "%~dp0"

python --version > nul 2>&1
if errorlevel 1 (
    echo Python이 설치되어 있지 않습니다.
    echo https://www.python.org 에서 설치한 뒤 다시 실행하세요.
    echo 설치할 때 "Add Python to PATH" 를 반드시 체크하세요.
    pause
    exit /b 1
)

python -c "import pypdf" > nul 2>&1
if errorlevel 1 (
    echo 처음 실행입니다. 필요한 부품을 설치합니다. 잠시 기다려 주세요.
    python -m pip install pypdf
    if errorlevel 1 (
        echo 설치에 실패했습니다. 인터넷 연결을 확인하세요.
        pause
        exit /b 1
    )
)

python scan_organizer.py
if errorlevel 1 pause
