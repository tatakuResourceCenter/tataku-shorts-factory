@echo off
chcp 65001 >nul
cd /d "%~dp0"
title 쇼츠 음성 생성

echo ============================================
echo    타입캐스트 쇼츠 음성 생성
echo ============================================
echo.
echo [0/3] 파이썬 찾는 중...

set PY=
py -3 -c "import sys" >nul 2>&1 && set PY=py -3
if not defined PY python -c "import sys" >nul 2>&1 && set PY=python
if not defined PY python3 -c "import sys" >nul 2>&1 && set PY=python3
if not defined PY if exist "%USERPROFILE%\anaconda3\python.exe" set PY="%USERPROFILE%\anaconda3\python.exe"
if not defined PY if exist "%USERPROFILE%\miniconda3\python.exe" set PY="%USERPROFILE%\miniconda3\python.exe"
if not defined PY if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" set PY="%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
if not defined PY if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" set PY="%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
if not defined PY if exist "%LOCALAPPDATA%\Programs\Python\Python310\python.exe" set PY="%LOCALAPPDATA%\Programs\Python\Python310\python.exe"
if not defined PY goto nopython

echo       찾음: %PY%

if exist "apikey.txt" set /p TYPECAST_API_KEY=<apikey.txt
if defined TYPECAST_API_KEY echo [키] apikey.txt 에서 불러왔습니다.
if not defined TYPECAST_API_KEY set /p TYPECAST_API_KEY=API 키를 붙여넣고 Enter: 
echo.

echo [1/3] 라이브러리 설치 확인...
%PY% -m pip install --quiet --upgrade typecast-python
echo.

echo [2/3] 플랜 / 크레딧 확인
%PY% shorts_tts.py --check
echo.

echo [3/3] 목소리 선택 후 음성 생성
echo       ** 번호만 입력하면 됩니다 (voice_id 타이핑 불필요) **
%PY% shorts_tts.py --voices-only
echo.
echo ============================================
echo  끝났습니다!
echo  Claude 에게 "음성 다 뽑았어" 라고 알려주세요.
echo ============================================
pause
exit /b

:nopython
echo.
echo  파이썬을 찾지 못했습니다.
echo.
echo  시작 메뉴에서 "Anaconda Prompt" 를 열고 아래를 붙여넣으세요:
echo.
echo     cd /d "%%USERPROFILE%%\Desktop\쇼츠작업"
echo     python -m pip install typecast-python
echo     set /p TYPECAST_API_KEY=^<apikey.txt
echo     python shorts_tts.py --voices-only
echo.
pause
