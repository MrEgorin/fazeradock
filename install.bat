@echo off
echo ============================================
echo   FazeraDock - Installing Dependencies
echo ============================================
echo.

REM Try to find Python 3 from PyMOL installation
set PYTHON_EXE=C:\pymol\python.exe

if not exist "%PYTHON_EXE%" (
    echo [WARNING] PyMOL Python not found at %PYTHON_EXE%
    echo Trying system Python...
    set PYTHON_EXE=python
)

echo Using Python: %PYTHON_EXE%
"%PYTHON_EXE%" --version
echo.

echo Installing matplotlib...
"%PYTHON_EXE%" -m pip install matplotlib --quiet
echo.

echo Installing scipy...
"%PYTHON_EXE%" -m pip install scipy --quiet
echo.

echo.
echo ============================================
echo   Installation Complete!
echo ============================================
echo.
echo Run FazeraDock with: run_fazeradock.bat
echo.
pause
