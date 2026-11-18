@echo off
chcp 65001 >nul
cd /d "%~dp0"
title 목소리 찾기

set PY=
py -3 -c "import sys" >nul 2>&1 && set PY=py -3
if not defined PY python -c "import sys" >nul 2>&1 && set PY=python
if not defined PY if exist "%USERPROFILE%\anaconda3\python.exe" set PY="%USERPROFILE%\anaconda3\python.exe"
if not defined PY goto nopython

if exist "apikey.txt" set /p TYPECAST_API_KEY=<apikey.txt

echo ============================================
echo    타입캐스트 목소리 찾기
echo ============================================
echo.
echo  쓰시는 목소리 이름을 띄어쓰기로 구분해 넣으세요.
echo  예) 문정 아찌 수아 베리 호빈이 서윤
echo  그냥 Enter 를 치면 전체 목록을 봅니다.
echo.
set /p NAMES=이름: 
echo.
%PY% shorts_tts.py --list %NAMES%
echo.
pause
exit /b

:nopython
echo python 을 찾지 못했습니다. Anaconda Prompt 에서 실행하세요.
pause
