@echo off
setlocal

taskkill /FI "WINDOWTITLE eq MockGenerator Backend*" /T /F >nul 2>nul
taskkill /IM "mockgenerator-backend.exe" /F >nul 2>nul

echo MockGenerator backend stopped.
endlocal
