# Windows One-Click Installer Build

This project can be distributed as a Windows installer with a desktop shortcut.

## 1) Build backend executable

From repository root, run:

```bat
packaging\windows\build-backend-exe.bat
```

Expected output folder:

- `backend\dist\mockgenerator-backend\`

## 2) Build frontend static files

```bat
cd mockup-tool-frontend
npm install
npm run build
```

Expected output folder:

- `mockup-tool-frontend\dist\`

## 3) Build installer EXE (Inno Setup)

- Install Inno Setup.
- Open `packaging\windows\MockGeneratorInstaller.iss`.
- Click **Compile**.

Output:

- `packaging\windows\MockGeneratorInstaller.exe`

## 4) Share with users

- Zip and share the installer EXE.
- User runs installer, picks location, and finishes setup.
- Desktop shortcut **Mock Generator** is created.

## Runtime behavior

Desktop shortcut starts local backend and opens browser at:

- `http://127.0.0.1:8000`

Data is stored in:

- `%LOCALAPPDATA%\MockGenerator\data`

Logs are written to:

- `%LOCALAPPDATA%\MockGenerator\logs\backend.log`

## Notes

- This distribution is Windows-only.
- If `mockgenerator-backend.exe` is missing, launcher falls back to `python desktop_server.py`.
- Uninstall entry is added in Start Menu, and uninstall removes `%LOCALAPPDATA%\MockGenerator\data`.
