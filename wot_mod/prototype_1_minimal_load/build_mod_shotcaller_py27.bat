@echo off
setlocal

if "%~1"=="" (
    echo Usage: build_mod_shotcaller_py27.bat C:\Python27\python.exe
    exit /b 1
)

set PY27=%~1

if not exist "%PY27%" (
    echo Python 2.7 executable not found: %PY27%
    exit /b 1
)

"%PY27%" -m py_compile mod_shotcaller.py
if errorlevel 1 (
    echo Python 2.7 compile failed.
    exit /b 1
)

if exist mod_shotcaller.pyc (
    echo Built mod_shotcaller.pyc
    exit /b 0
)

echo Compile command finished but mod_shotcaller.pyc was not found.
exit /b 1
