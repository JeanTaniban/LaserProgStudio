@echo off
setlocal
call "%~dp0scripts\run_laserprog_studio.bat" %*
set "LAUNCH_EXIT=%ERRORLEVEL%"
endlocal & exit /b %LAUNCH_EXIT%
