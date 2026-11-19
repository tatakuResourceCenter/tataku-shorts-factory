@echo off
chcp 65001 >nul
cd /d "%~dp0"
title 쇼츠 공방 편집기

set PY=
py -3 -c "import sys" >nul 2>&1 && set PY=py -3
if not defined PY python -c "import sys" >nul 2>&1 && set PY=python
if not defined PY python3 -c "import sys" >nul 2>&1 && set PY=python3
if not defined PY if exist "%USERPROFILE%\anaconda3\python.exe" set PY="%USERPROFILE%\anaconda3\python.exe"
if not defined PY if exist "%USERPROFILE%\miniconda3\python.exe" set PY="%USERPROFILE%\miniconda3\python.exe"
if not defined PY if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" set PY="%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
if not defined PY if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" set PY="%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
if not defined PY goto nopython

echo 필요한 라이브러리 확인 중...
%PY% -m pip install --quiet --upgrade typecast-python pillow imageio-ffmpeg
echo.
echo 편집기를 켜는 중입니다. 잠시 후 브라우저가 열려요.
echo 이 검은 창을 닫으면 편집기도 꺼집니다.
echo.
rem ── 예전 편집기가 켜져 있으면 먼저 끄기 ──
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":8765" ^| findstr LISTENING') do taskkill /PID %%p /F >nul 2>&1
%PY% editor_server.py
if errorlevel 1 (
  echo.
  echo 편집기가 오류로 꺼졌습니다. 위 메시지를 Claude 에게 보여주세요.
  pause
)
exit /b

:nopython
echo 파이썬을 찾지 못했습니다. Anaconda Prompt 에서 실행하세요:
echo    cd /d "%%USERPROFILE%%\Desktop\쇼츠작업"
echo    python editor_server.py
pause
