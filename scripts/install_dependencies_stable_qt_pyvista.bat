@echo off
setlocal
REM Compatibility wrapper kept for older shortcuts.
call "%~dp0install_dependencies.bat" %*
set "INSTALL_EXIT=%ERRORLEVEL%"
endlocal & exit /b %INSTALL_EXIT%
