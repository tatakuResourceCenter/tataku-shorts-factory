@echo off
chcp 65001 >nul
cd /d "%~dp0"
title 대본 편집기

set PY=
pythonw -c "import sys" >nul 2>&1 && set PY=pythonw
if not defined PY py -3 -c "import sys" >nul 2>&1 && set PY=py -3
if not defined PY python -c "import sys" >nul 2>&1 && set PY=python
if not defined PY if exist "%USERPROFILE%\anaconda3\pythonw.exe" set PY="%USERPROFILE%\anaconda3\pythonw.exe"
if not defined PY if exist "%USERPROFILE%\anaconda3\python.exe" set PY="%USERPROFILE%\anaconda3\python.exe"
if not defined PY goto nopython

%PY% -m pip install --quiet --upgrade typecast-python
%PY% 대본편집기.py
if errorlevel 1 (
  echo.
  echo 편집기가 오류로 종료됐습니다.
  echo 같은 폴더의 오류기록.txt 를 Claude 에게 보여주세요.
  pause
)
exit /b

:nopython
echo 파이썬을 찾지 못했습니다. Anaconda Prompt 에서 실행하세요:
echo    cd /d "%%USERPROFILE%%\Desktop\쇼츠작업"
echo    python 대본편집기.py
pause
