@echo off
setlocal

cd /d "%~dp0\..\..\backend"

set "PYEXE="
if exist ".venv\Scripts\python.exe" set "PYEXE=%CD%\.venv\Scripts\python.exe"
if exist "venv\Scripts\python.exe" set "PYEXE=%CD%\venv\Scripts\python.exe"

if "%PYEXE%"=="" (
  echo [ERROR] No Python venv found in backend\.
  echo Create one with:  cd backend ^&^& python -m venv venv  ^(or .venv^)
  exit /b 1
)

"%PYEXE%" -m pip install --upgrade pip
"%PYEXE%" -m pip install -r requirements.txt pyinstaller

if exist build rmdir /s /q build
if exist dist\mockgenerator-backend rmdir /s /q dist\mockgenerator-backend

"%PYEXE%" -m PyInstaller ^
  --name mockgenerator-backend ^
  --onedir ^
  --noconfirm ^
  --clean ^
  --hidden-import api ^
  --hidden-import script ^
  --hidden-import cv2 ^
  --hidden-import numpy ^
  --hidden-import scipy ^
  --hidden-import PIL ^
  --hidden-import fastapi ^
  --hidden-import pydantic ^
  --hidden-import uvicorn ^
  desktop_server.py

if errorlevel 1 (
  echo [ERROR] Backend EXE build failed.
  exit /b 1
)

echo [OK] Built backend EXE at backend\dist\mockgenerator-backend\
endlocal
