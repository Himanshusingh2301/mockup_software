# Mock Generator

A full-stack tool for placing images into phone-frame mockups: **Python** handles detection and compositing (OpenCV, NumPy, SciPy, Pillow); **FastAPI** exposes a REST API; a **React + Vite + Tailwind** UI uploads mockups and inputs, edits templates per use case, and downloads generated outputs.

You can run it **during development** (backend + frontend dev servers) or **ship a Windows desktop build** (single installer: packaged backend + static frontend, no Python/Node required for end users).

---

## Features

- **Mockups & inputs** managed in the browser; images are uploaded to the server only for processing (outputs are fetched from the API).
- **Templates / use cases** (simple tilted, simple flat, overlay with hands, etc.) configurable in the UI with validation aligned to the backend.
- **Per-user workspaces** via an anonymous **workspace user ID** (created once, stored in `localStorage`, registered on the server). Outputs and uploads are isolated per ID.
- **Desktop mode**: one local URL serves both API and built SPA; data stored under `%LOCALAPPDATA%\MockGenerator\data` on Windows.

---

## Repository layout

| Path | Purpose |
|------|---------|
| `backend/` | FastAPI app (`api.py`), image pipeline (`script.py`), packaged entrypoint (`desktop_server.py`), `requirements.txt` |
| `mockup-tool-frontend/` | React SPA (Vite), `npm run build` → `dist/` |
| `packaging/windows/` | PyInstaller script, Inno Setup installer, launcher batch files |

Runtime artifacts (workspace DB, temp uploads, PyInstaller output) are normally gitignored—see `.gitignore`.

---

## Prerequisites (development only)

- **Python 3** (with venv recommended under `backend/venv` or `backend/.venv`)
- **Node.js** (for frontend install/build)

End users who install **only** `MockGeneratorInstaller.exe` do **not** need Python or Node.

---

## Backend setup

From the repository root:

```powershell
cd backend
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Run the API (development):

```powershell
cd backend
.\venv\Scripts\Activate.ps1
python -m uvicorn api:app --reload --host 127.0.0.1 --port 8000
```

Health check: `GET http://127.0.0.1:8000/api/health`

---

## Frontend setup

```powershell
cd mockup-tool-frontend
npm install
```

Create `.env` from the example (optional; defaults match local backend):

```powershell
copy .env.example .env
```

Key variable:

- **`VITE_API_BASE_URL`** — API origin (no trailing slash), e.g. `http://127.0.0.1:8000`.

Development server:

```powershell
npm run dev
```

Production build:

```powershell
npm run build
```

Output: `mockup-tool-frontend/dist/`.

---

## Running modes

### A. Split dev (typical while coding)

1. Backend: `python -m uvicorn api:app --reload --host 127.0.0.1 --port 8000`
2. Frontend: `npm run dev` (Vite proxies/hits `VITE_API_BASE_URL`)

CORS: set **`FRONTEND_ORIGIN`** on the backend to your Vite origin if it is not `http://127.0.0.1:8000` (see environment variables below).

### B. Single origin “desktop style” (API + built SPA)

After `npm run build`, point the backend at the frontend `dist` folder and open the same host/port as the API:

- Set **`MOCKGENERATOR_FRONTEND_DIST`** to the absolute path of `mockup-tool-frontend/dist`.
- Set **`FRONTEND_ORIGIN`** to that server’s public URL (e.g. `http://127.0.0.1:8000`).
- Run `python -m uvicorn api:app --host 127.0.0.1 --port 8000`

Or use **`desktop_server.py`** (used by the packaged `.exe`): it sets sensible defaults, `cd`s into `backend`, and runs Uvicorn with the imported app.

```powershell
cd backend
.\venv\Scripts\Activate.ps1
python desktop_server.py
```

Then open `http://127.0.0.1:8000` (or the port set by **`MOCKGENERATOR_PORT`**).

---

## Environment variables (backend)

| Variable | Purpose |
|----------|---------|
| `MOCKGENERATOR_DATA_ROOT` | Root for `workspace_data/` and `workspace_users.json`. Defaults next to `backend` when unset; packaged launcher sets `%LOCALAPPDATA%\MockGenerator\data`. |
| `MOCKGENERATOR_FRONTEND_DIST` | Absolute path to the built SPA (`dist`). When present and `index.html` exists, `/` serves the UI. |
| `FRONTEND_ORIGIN` | CORS allowlist (comma-separated origins). Must not end with `/`. If unset, permissive CORS for tooling. |
| `MOCKGENERATOR_PORT` | Listen port for `desktop_server.py` (default `8000`). |
| `MOCKGENERATOR_RUN_INPROCESS` | Set to `1` to run generation inside the API process (used for packaged exe / desktop). |

`script.py` also honors **`MOCKGENERATOR_*`** paths when the API runs generation via subprocess (non-frozen dev); the API sets these per workspace when needed.

---

## Workspace user ID

- Users choose or paste a **workspace user ID** in the UI; it is sent as **`X-Workspace-User-Id`** (and where needed as a query parameter for asset URLs).
- The backend registers IDs and stores data under **`workspace_data/<user_id>/`** inside **`MOCKGENERATOR_DATA_ROOT`**.
- For hosted deployments, point **`MOCKGENERATOR_DATA_ROOT`** at persistent disk if you need data to survive restarts.

---

## Windows installer (distribution)

Building the installer is **only for maintainers** who package the app. End users run **`MockGeneratorInstaller.exe`** only.

1. **Frontend:** `cd mockup-tool-frontend` → `npm install` → `npm run build`
2. **Backend exe:** `packaging\windows\build-backend-exe.bat` → output under `backend\dist\mockgenerator-backend\`
3. **Installer:** open `packaging\windows\MockGeneratorInstaller.iss` in **Inno Setup** → Compile (F9) → `MockGeneratorInstaller.exe`

Details and paths: `packaging/windows/BUILD_WINDOWS_INSTALLER.md`.

Installed app:

- Shortcut runs **`start-mockgenerator.bat`**, waits for **`/api/health`**, opens the browser.
- Logs: `%LOCALAPPDATA%\MockGenerator\logs\backend.log`
- User data: `%LOCALAPPDATA%\MockGenerator\data`

Uninstall can remove that data per the Inno script.

---

## Troubleshooting

- **`Could not import module "api"` (frozen exe):** Rebuild with current `desktop_server.py` (imports `app` directly) and run `build-backend-exe.bat` again.
- **CORS errors in the browser:** Align **`FRONTEND_ORIGIN`** with the exact origin of your frontend (scheme + host + port, no trailing slash).
- **Generation errors:** Check server logs; packaged runs log to `backend.log` above.

---

## Tech stack

- **Backend:** FastAPI, Uvicorn, Pydantic, Pillow, NumPy, SciPy, OpenCV (`opencv-python`)
- **Frontend:** React 19, Vite 8, Tailwind CSS 4, ESLint
- **Desktop packaging:** PyInstaller (`desktop_server.py`), Inno Setup, launcher `.bat` scripts

