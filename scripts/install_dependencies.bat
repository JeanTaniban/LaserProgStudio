@echo off
setlocal EnableExtensions EnableDelayedExpansion

REM LaserProg Studio dependency installer.
REM The batch file only selects Python 3.12.x. The Python helper owns all
REM installation decisions and treats the final dependency check as authoritative.

set "PAUSE_ON_EXIT=1"
if /I "%~1"=="--no-pause" set "PAUSE_ON_EXIT=0"

set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%..") do set "ROOT=%%~fI"
cd /d "%ROOT%" || goto :fatal_cd

if not exist "diagnostics" mkdir "diagnostics" >nul 2>nul
set "LOG=%ROOT%\diagnostics\setup_dependencies.log"

call :find_python
if not defined PY_EXE goto :no_python

"%PY_EXE%" %PY_ARGS% "%ROOT%\scripts\setup_dependencies.py" --root "%ROOT%" --log "%LOG%"
set "SETUP_EXIT=!ERRORLEVEL!"

echo.
if "!SETUP_EXIT!"=="0" (
    echo Setup succeeded.
    echo You can now run RUN_LASERPROG_STUDIO.bat
) else (
    echo Setup failed.
    echo See the log file:
    echo   %LOG%
)
echo.
if "%PAUSE_ON_EXIT%"=="1" pause
endlocal & exit /b %SETUP_EXIT%

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
echo ----------------------------------------
echo LaserProg Studio dependency setup
echo Required Python: 3.12.x
echo ERROR: Python 3.12.x was not found.
echo Install any stable Python 3.12 release from python.org.
echo If it is already installed, run this command and send the output: py -0p
echo ----------------------------------------
> "%LOG%" echo RESULT: FAILURE
>> "%LOG%" echo ERROR: Python 3.12.x was not found.
>> "%LOG%" echo Run py -0p to list installed Python interpreters.
if "%PAUSE_ON_EXIT%"=="1" pause
endlocal & exit /b 1

:fatal_cd
echo ERROR: Could not enter project folder.
if "%PAUSE_ON_EXIT%"=="1" pause
endlocal & exit /b 1
