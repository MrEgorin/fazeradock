@echo off
echo Starting FazeraDock...

REM Use PyMOL's Python 3.10 environment
set PYTHON_EXE=C:\pymol\python.exe
set SCRIPT_DIR=%~dp0

if not exist "%PYTHON_EXE%" (
    echo [ERROR] Python not found at %PYTHON_EXE%
    echo Please install PyMOL open-source or update the path in this script.
    pause
    exit /b 1
)

REM Add OpenBabel to PATH
set PATH=C:\Program Files\OpenBabel-3.1.1;C:\openbabel-3.1.1;%PATH%

REM Run FazeraDock
"%PYTHON_EXE%" "%SCRIPT_DIR%run_fazeradock.py"
