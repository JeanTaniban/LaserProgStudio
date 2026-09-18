@echo off
setlocal EnableExtensions

REM LaserProg Studio launcher.
REM This script launches the app with the selected central Python.
REM No virtual environment is used or created.
REM IMPORTANT: LaserProg runtime accepts the Python 3.12.x series.

title LaserProg Studio

set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%..") do set "ROOT=%%~fI"
cd /d "%ROOT%" || goto :fatal_cd

if not exist "diagnostics" mkdir "diagnostics" >nul 2>nul
set "RUN_LOG=%ROOT%\diagnostics\run_launcher.log"

echo ---------------------------------------- > "%RUN_LOG%"
echo LaserProg Studio launcher >> "%RUN_LOG%"
echo Launch mode: central Python, no venv >> "%RUN_LOG%"
echo Required Python: 3.12.x >> "%RUN_LOG%"
echo Root: %ROOT% >> "%RUN_LOG%"
echo ---------------------------------------- >> "%RUN_LOG%"

call :find_python
if not defined PY_EXE goto :no_python

echo Selected command: "%PY_EXE%" %PY_ARGS% >> "%RUN_LOG%"
"%PY_EXE%" %PY_ARGS% -c "import sys; print('Selected version: '+str(sys.version_info.major)+'.'+str(sys.version_info.minor)+'.'+str(sys.version_info.micro)); print('Python executable: '+sys.executable)" >> "%RUN_LOG%" 2>&1

"%PY_EXE%" %PY_ARGS% -c "import sys; raise SystemExit(0 if sys.version_info[:2] == (3, 12) else 1)" >nul 2>nul
if errorlevel 1 (
    echo ERROR: LaserProg requires Python 3.12.x. >> "%RUN_LOG%"
    goto :fail
)

"%PY_EXE%" %PY_ARGS% "%ROOT%\scripts\check_dependencies.py" >> "%RUN_LOG%" 2>&1
if errorlevel 1 (
    echo.
    echo Some dependencies are missing or do not match the pinned LaserProg runtime versions.
    echo Run INSTALL_DEPENDENCIES.bat first, then run this launcher again.
    echo.
    echo Dependency pin check failed. Installer required. >> "%RUN_LOG%"
    goto :fail
)

set "PYTHONPATH=%ROOT%\src"
set "QT_OPENGL=desktop"
set "QT_ENABLE_HIGHDPI_SCALING=0"
set "PYVISTA_OFF_SCREEN=false"
set "QT_LOGGING_RULES=qt.qpa.*=false"

echo Starting LaserProg Studio...
echo PYTHONPATH: %PYTHONPATH% >> "%RUN_LOG%"

"%PY_EXE%" %PY_ARGS% "%ROOT%\run.py" >> "%RUN_LOG%" 2>&1
set "APP_EXIT=%ERRORLEVEL%"

if not "%APP_EXIT%"=="0" (
    echo.
    echo LaserProg Studio stopped with exit code %APP_EXIT%.
    echo Check these logs:
    echo   %RUN_LOG%
    echo   %ROOT%\diagnostics\laserprog_studio_v18.log
    echo.
    pause
    exit /b %APP_EXIT%
)

exit /b 0

:find_python
set "PY_EXE="
set "PY_ARGS="
call :try_python py -3.12
if defined PY_EXE exit /b 0
call :try_python python
if defined PY_EXE exit /b 0
call :try_python "%LocalAppData%\Programs\Python\Python312\python.exe"
if defined PY_EXE exit /b 0
call :try_python "%ProgramFiles%\Python312\python.exe"
if defined PY_EXE exit /b 0
call :try_python "%ProgramFiles(x86)%\Python312\python.exe"
if defined PY_EXE exit /b 0
call :try_python py -3
if defined PY_EXE exit /b 0
exit /b 1

:try_python
set "CANDIDATE_EXE=%~1"
set "CANDIDATE_ARGS=%~2"
if "%CANDIDATE_EXE%"=="" exit /b 0
"%CANDIDATE_EXE%" %CANDIDATE_ARGS% -c "import sys; raise SystemExit(0 if sys.version_info[:2] == (3, 12) else 1)" >nul 2>nul
if not errorlevel 1 (
    set "PY_EXE=%CANDIDATE_EXE%"
    set "PY_ARGS=%CANDIDATE_ARGS%"
)
exit /b 0

:no_python
echo.
echo ERROR: Python 3.12.x was not found.
echo Install any stable Python 3.12 release from python.org.
echo If it is already installed, run this command and send the output: py -0p
echo.
echo ERROR: Python 3.12.x was not found. >> "%RUN_LOG%"
goto :fail

:fatal_cd
echo ERROR: Could not enter project folder.
pause
exit /b 1

:fail
echo.
echo Launch failed.
echo Check this log:
echo   %RUN_LOG%
echo.
pause
exit /b 1
