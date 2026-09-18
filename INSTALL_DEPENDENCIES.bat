@echo off
setlocal
call "%~dp0scripts\install_dependencies.bat" %*
set "INSTALL_EXIT=%ERRORLEVEL%"
endlocal & exit /b %INSTALL_EXIT%
