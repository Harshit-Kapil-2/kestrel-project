@echo off
title PostFinder Desktop
cd /d "%~dp0"

echo ===================================================
echo             Starting PostFinder Desktop
echo ===================================================
echo.

where py >nul 2>nul
if %ERRORLEVEL% EQU 0 (
    py -3.11 desktop.py
    if %ERRORLEVEL% NEQ 0 (
        py desktop.py
    )
    goto end
)

where python >nul 2>nul
if %ERRORLEVEL% EQU 0 (
    python desktop.py
    goto end
)

echo ERROR: Python was not found in your system PATH!
echo Please ensure Python 3.11+ is installed.
echo.
pause

:end
