@echo off
setlocal

set "SCRIPT_DIR=%~dp0"
set "TEMP_PACKAGE=%SCRIPT_DIR%temp_package"
set "DIST_DIR=%SCRIPT_DIR%dist"
set "OUTPUT_NAME=shotcaller_0.0.1_raw_py.wotmod"
set "SOURCE_FILE=%SCRIPT_DIR%mod_shotcaller.py"
set "HELPER_SCRIPT=%SCRIPT_DIR%build_raw_py_wotmod.py"

where python.exe >nul 2>&1
if errorlevel 1 (
    echo Python 3 is required to create the uncompressed .wotmod package.
    exit /b 1
)

if not exist "%SOURCE_FILE%" (
    echo Source file not found: %SOURCE_FILE%
    exit /b 1
)

if not exist "%HELPER_SCRIPT%" (
    echo Helper script not found: %HELPER_SCRIPT%
    exit /b 1
)

python.exe -c "import sys; sys.exit(0 if sys.version_info[0] == 3 else 1)"
if errorlevel 1 (
    echo Python 3 is required; the detected Python is not Python 3.
    exit /b 1
)

if exist "%TEMP_PACKAGE%" rmdir /s /q "%TEMP_PACKAGE%"
if exist "%DIST_DIR%\%OUTPUT_NAME%" del /q "%DIST_DIR%\%OUTPUT_NAME%"

mkdir "%TEMP_PACKAGE%\res\scripts\client\gui\mods" || goto failed
if not exist "%DIST_DIR%" mkdir "%DIST_DIR%"
if not exist "%DIST_DIR%" goto failed
copy /y "%SOURCE_FILE%" "%TEMP_PACKAGE%\res\scripts\client\gui\mods\mod_shotcaller.py" >nul || goto failed

python.exe "%HELPER_SCRIPT%" "%TEMP_PACKAGE%" "%DIST_DIR%\%OUTPUT_NAME%"
if errorlevel 1 goto failed

if not exist "%DIST_DIR%\%OUTPUT_NAME%" goto failed

rmdir /s /q "%TEMP_PACKAGE%"
echo Built %DIST_DIR%\%OUTPUT_NAME%
exit /b 0

:failed
if exist "%TEMP_PACKAGE%" rmdir /s /q "%TEMP_PACKAGE%"
echo Failed to build the raw-Python .wotmod package.
exit /b 1
