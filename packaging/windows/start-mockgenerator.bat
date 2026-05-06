@echo off
setlocal EnableExtensions

rem Resolve app root (installation folder) reliably — shortcuts may use a wrong working directory.
for %%I in ("%~dp0..") do set "APP_ROOT=%%~fI"
set "BACKEND_DIR=%APP_ROOT%\backend"
set "FRONTEND_DIST=%APP_ROOT%\frontend\dist"
set "DATA_ROOT=%LOCALAPPDATA%\MockGenerator\data"
set "LOG_DIR=%LOCALAPPDATA%\MockGenerator\logs"
set "LOG_FILE=%LOG_DIR%\backend.log"
set "PORT=8000"

if not exist "%DATA_ROOT%" mkdir "%DATA_ROOT%"
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"

set "MOCKGENERATOR_DATA_ROOT=%DATA_ROOT%"
set "MOCKGENERATOR_FRONTEND_DIST=%FRONTEND_DIST%"
set "MOCKGENERATOR_PORT=%PORT%"
set "FRONTEND_ORIGIN=http://127.0.0.1:%PORT%"
set "HEALTH_URL=http://127.0.0.1:%PORT%/api/health"
set "APP_URL=http://127.0.0.1:%PORT%"

title Mock Generator
echo.
echo Mock Generator — starting...
echo App:     %APP_ROOT%
echo Backend: %BACKEND_DIR%
echo Log:     %LOG_FILE%
echo.

call :healthcheck
if not errorlevel 1 goto open_app

if exist "%BACKEND_DIR%\mockgenerator-backend.exe" goto start_packaged
goto start_python

:start_packaged
echo Starting packaged backend...
rem Correct cmd.exe quoting: doubled quote after /c, no backslashes before quotes.
start "MockGenerator Backend" /min cmd.exe /c ""%BACKEND_DIR%\mockgenerator-backend.exe" >>"%LOG_FILE%" 2>&1"
goto wait_ready

:start_python
if not exist "%BACKEND_DIR%\desktop_server.py" (
  echo [ERROR] Backend not found under:
  echo         %BACKEND_DIR%
  echo Install the app again or rebuild the installer.
  pause
  goto :eof
)
where python >nul 2>nul
if errorlevel 1 (
  echo [ERROR] Python is not on PATH. Install Python or use the packaged backend exe.
  pause
  goto :eof
)
echo Starting backend with Python...
rem Working directory set via /D avoids broken nested quotes in cmd /c.
start "MockGenerator Backend" /min /D "%BACKEND_DIR%" cmd.exe /c python desktop_server.py 1>>"%LOG_FILE%" 2>>&1

:wait_ready
echo Waiting for backend at %HEALTH_URL% ...
set "ATTEMPTS=60"
:wait_loop
call :healthcheck
if not errorlevel 1 goto open_app
set /a ATTEMPTS-=1
if %ATTEMPTS% LEQ 0 goto failed
timeout /t 1 /nobreak >nul
goto wait_loop

:open_app
echo Backend is ready. Opening browser...
start "" "%APP_URL%"
echo.
echo You can close this window. To stop the server, use "Stop Mock Generator" in the Start menu.
timeout /t 3 /nobreak >nul
goto :eof

:failed
echo.
echo [ERROR] Backend did not respond in time.
echo Open the log file for details:
echo   %LOG_FILE%
echo.
echo Tips: check antivirus blocking the exe, or another program using port %PORT%.
pause
goto :eof

:healthcheck
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "try { $r = Invoke-WebRequest -UseBasicParsing -Uri '%HEALTH_URL%' -TimeoutSec 3; if ($r.StatusCode -eq 200) { exit 0 } else { exit 1 } } catch { exit 1 }" >nul 2>&1
if errorlevel 1 exit /b 1
exit /b 0
