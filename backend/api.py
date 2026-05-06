import json
import os
import shutil
import subprocess
import sys
import tempfile
from contextlib import redirect_stdout
from datetime import datetime, timezone
from io import StringIO
from pathlib import Path
from typing import Annotated, Literal
from urllib.parse import quote, unquote

from fastapi import Depends, FastAPI, File, Header, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

import script

BASE_DIR = Path(__file__).resolve().parent
# Packaged desktop exe: persist workspaces outside the PyInstaller bundle via MOCKGENERATOR_DATA_ROOT.
DATA_ROOT = Path(os.getenv("MOCKGENERATOR_DATA_ROOT", str(BASE_DIR))).resolve()
WORKSPACE_DATA_DIR = DATA_ROOT / "workspace_data"
WORKSPACE_USERS_PATH = DATA_ROOT / "workspace_users.json"
TEMP_ROOT_DIR = Path(tempfile.gettempdir()) / "mockgenerator"
FRONTEND_DIST_DIR = Path(
    os.getenv("MOCKGENERATOR_FRONTEND_DIST", str(BASE_DIR.parent / "mockup-tool-frontend" / "dist"))
).resolve()
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}


def workspace_paths(user_id: str) -> dict[str, Path]:
    """Per-user mockups, inputs, outputs, template file, and temp upload dirs."""
    root = WORKSPACE_DATA_DIR / user_id
    return {
        "root": root,
        "mockups": root / "mockups",
        "inputs": root / "input_images",
        "outputs": root / "output",
        "template_config": root / "template_config.json",
        "temp_mockups": TEMP_ROOT_DIR / user_id / "mockups",
        "temp_inputs": TEMP_ROOT_DIR / user_id / "input_images",
    }


def ensure_workspace_tree(paths: dict[str, Path]) -> None:
    for key in ("mockups", "inputs", "outputs"):
        paths[key].mkdir(parents=True, exist_ok=True)
    paths["temp_mockups"].mkdir(parents=True, exist_ok=True)
    paths["temp_inputs"].mkdir(parents=True, exist_ok=True)


def ensure_dirs() -> None:
    WORKSPACE_DATA_DIR.mkdir(parents=True, exist_ok=True)
    TEMP_ROOT_DIR.mkdir(parents=True, exist_ok=True)


def _frontend_index_path() -> Path:
    return FRONTEND_DIST_DIR / "index.html"


def _frontend_is_available() -> bool:
    return _frontend_index_path().exists()


def _frontend_file_or_index(full_path: str) -> FileResponse:
    """
    Serve built frontend assets for local desktop mode.
    Unknown paths fall back to index.html for SPA routing.
    """
    if not _frontend_is_available():
        raise HTTPException(status_code=404, detail="Frontend build not found.")

    rel = full_path.lstrip("/")
    if rel:
        candidate = (FRONTEND_DIST_DIR / rel).resolve()
        if FRONTEND_DIST_DIR in candidate.parents and candidate.exists() and candidate.is_file():
            return FileResponse(candidate)

    return FileResponse(_frontend_index_path())


def safe_name(name: str) -> str:
    cleaned = "".join(ch for ch in name if ch not in '\\/:*?"<>|').strip()
    if not cleaned:
        raise HTTPException(status_code=400, detail="Invalid file name.")
    return cleaned


def safe_join(base: Path, name: str) -> Path:
    resolved = (base / name).resolve()
    if base.resolve() not in resolved.parents and resolved != base.resolve():
        raise HTTPException(status_code=400, detail="Invalid path.")
    return resolved


def list_images(folder: Path, url_prefix: str):
    files = []
    for file in sorted(folder.iterdir()):
        if file.is_file() and file.suffix.lower() in IMAGE_SUFFIXES:
            stat = file.stat()
            files.append(
                {
                    "id": file.name,
                    "name": file.name,
                    "displayName": file.name,
                    "url": url_prefix + quote(file.name),
                    "size": stat.st_size,
                    "modified": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
                }
            )
    return files


def list_outputs(output_root: Path):
    files = []
    output_root.mkdir(parents=True, exist_ok=True)
    if not output_root.exists():
        return files
    for file in sorted(output_root.rglob("*")):
        if file.is_file() and file.suffix.lower() in IMAGE_SUFFIXES:
            rel = file.relative_to(output_root).as_posix()
            stat = file.stat()
            files.append(
                {
                    "id": rel,
                    "name": rel,
                    "displayName": rel,
                    "url": f"/api/files/output/{quote(rel)}",
                    "size": stat.st_size,
                    "modified": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
                }
            )
    return files


def clear_folder(folder: Path):
    if folder.exists():
        shutil.rmtree(folder)
    folder.mkdir(parents=True, exist_ok=True)


def copy_images(src: Path, dst: Path):
    dst.mkdir(parents=True, exist_ok=True)
    clear_folder(dst)
    for file in src.iterdir():
        if file.is_file() and file.suffix.lower() in IMAGE_SUFFIXES:
            shutil.copy2(file, dst / file.name)


def read_user_templates(user_id: str):
    path = workspace_paths(user_id)["template_config"]
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return script.DEFAULT_TEMPLATES


def write_user_templates(user_id: str, templates) -> None:
    paths = workspace_paths(user_id)
    ensure_workspace_tree(paths)
    paths["template_config"].write_text(json.dumps(templates, indent=2), encoding="utf-8")


def validate_workspace_user_id(raw: str) -> str:
    """Same rules as frontend: single path segment, safe for future namespaced dirs."""
    trimmed = (raw or "").strip()
    if not trimmed:
        raise HTTPException(status_code=400, detail="User ID is required.")
    if len(trimmed) > 128:
        raise HTTPException(status_code=400, detail="User ID must be at most 128 characters.")
    if "/" in trimmed or "\\" in trimmed or ".." in trimmed:
        raise HTTPException(status_code=400, detail='User ID cannot contain "/", "\\", or "..".')
    return trimmed


def read_registered_workspace_users() -> list[dict]:
    if not WORKSPACE_USERS_PATH.exists():
        return []
    try:
        data = json.loads(WORKSPACE_USERS_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    if isinstance(data, dict) and isinstance(data.get("users"), list):
        return [u for u in data["users"] if isinstance(u, dict) and u.get("user_id")]
    return []


def append_registered_workspace_user(user_id: str) -> None:
    users = read_registered_workspace_users()
    existing = {str(u.get("user_id", "")) for u in users}
    if user_id in existing:
        raise HTTPException(
            status_code=409,
            detail="This user ID is already taken. Choose a different one.",
        )
    users.append(
        {
            "user_id": user_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
    )
    WORKSPACE_USERS_PATH.write_text(
        json.dumps({"users": users}, indent=2),
        encoding="utf-8",
    )


def registered_user_ids() -> set[str]:
    return {str(u.get("user_id", "")) for u in read_registered_workspace_users()}


def require_workspace_user(
    x_workspace_user_id: str | None = Header(None, alias="X-Workspace-User-Id"),
    workspace_user_id: str | None = Query(None),
) -> str:
    raw = (x_workspace_user_id or workspace_user_id or "").strip()
    if not raw:
        raise HTTPException(
            status_code=401,
            detail="Missing workspace user ID. Send header X-Workspace-User-Id.",
        )
    uid = validate_workspace_user_id(raw)
    if uid not in registered_user_ids():
        raise HTTPException(status_code=403, detail="Unknown workspace user ID.")
    return uid


WorkspaceUser = Annotated[str, Depends(require_workspace_user)]


class RenamePayload(BaseModel):
    new_name: str


class TemplatesPayload(BaseModel):
    templates: list


class GeneratePayload(BaseModel):
    templates: list | None = None


class WorkspaceRegisterPayload(BaseModel):
    user_id: str


app = FastAPI(title="Mock Generator API", version="1.0.0")

# CORS: never combine allow_origins=["*"] with allow_credentials=True (invalid for browsers).
# Origin header never has a trailing slash — strip trailing slashes from FRONTEND_ORIGIN or CORS won't match.
def _parse_cors_origins(raw: str) -> list[str]:
    out: list[str] = []
    for part in raw.split(","):
        u = part.strip().rstrip("/")
        if u:
            out.append(u)
    return out


_frontend_origin = os.getenv("FRONTEND_ORIGIN", "").strip()
if _frontend_origin:
    _cors_origins = _parse_cors_origins(_frontend_origin)
    if not _cors_origins:
        _cors_origins = ["*"]
        _cors_credentials = False
    else:
        _cors_credentials = True
else:
    _cors_origins = ["*"]
    _cors_credentials = False

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=_cors_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
    max_age=86400,
)


@app.on_event("startup")
def on_startup():
    ensure_dirs()


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/")
def root_health():
    if _frontend_is_available():
        return FileResponse(_frontend_index_path())
    return {"status": "ok", "service": "mockgenerator-api"}


@app.head("/")
def root_health_head():
    return JSONResponse(status_code=200, content=None)


@app.post("/api/workspace/register")
def register_workspace_user(payload: WorkspaceRegisterPayload):
    """Register a new workspace user ID. Rejects duplicates (409)."""
    user_id = validate_workspace_user_id(payload.user_id)
    append_registered_workspace_user(user_id)
    return {"ok": True, "user_id": user_id}


@app.post("/api/workspace/login")
def login_workspace_user(payload: WorkspaceRegisterPayload):
    """Confirm user ID exists (for returning users)."""
    user_id = validate_workspace_user_id(payload.user_id)
    existing = {str(u.get("user_id", "")) for u in read_registered_workspace_users()}
    if user_id not in existing:
        raise HTTPException(
            status_code=404,
            detail="No account found with this user ID. Create a new ID or check spelling.",
        )
    return {"ok": True, "user_id": user_id}


@app.get("/api/assets")
def get_assets(ws: WorkspaceUser):
    ensure_dirs()
    paths = workspace_paths(ws)
    ensure_workspace_tree(paths)
    return {
        "mockups": list_images(paths["mockups"], "/api/files/mockups/"),
        "inputs": list_images(paths["inputs"], "/api/files/inputs/"),
        "outputs": list_outputs(paths["outputs"]),
    }


@app.post("/api/upload/{kind}")
async def upload_files(ws: WorkspaceUser, kind: Literal["mockups", "inputs"], files: list[UploadFile] = File(...)):
    ensure_dirs()
    paths = workspace_paths(ws)
    ensure_workspace_tree(paths)
    target = paths["mockups"] if kind == "mockups" else paths["inputs"]
    for uploaded in files:
        name = safe_name(uploaded.filename or "file.png")
        path = safe_join(target, name)
        content = await uploaded.read()
        path.write_bytes(content)
    return JSONResponse({"ok": True})


@app.post("/api/upload-temp/mockups")
async def upload_mockups_temp(ws: WorkspaceUser, files: list[UploadFile] = File(...)):
    ensure_dirs()
    paths = workspace_paths(ws)
    ensure_workspace_tree(paths)
    clear_folder(paths["temp_mockups"])
    for uploaded in files:
        name = safe_name(uploaded.filename or "mockup.png")
        path = safe_join(paths["temp_mockups"], name)
        content = await uploaded.read()
        path.write_bytes(content)
    return JSONResponse({"ok": True})


@app.post("/api/upload-temp/inputs")
async def upload_inputs_temp(ws: WorkspaceUser, files: list[UploadFile] = File(...)):
    ensure_dirs()
    paths = workspace_paths(ws)
    ensure_workspace_tree(paths)
    clear_folder(paths["temp_inputs"])
    for uploaded in files:
        name = safe_name(uploaded.filename or "input.png")
        path = safe_join(paths["temp_inputs"], name)
        content = await uploaded.read()
        path.write_bytes(content)
    return JSONResponse({"ok": True})


@app.delete("/api/assets/{kind}/{name}")
def delete_asset(ws: WorkspaceUser, kind: Literal["mockups", "inputs", "outputs"], name: str):
    ensure_dirs()
    paths = workspace_paths(ws)
    ensure_workspace_tree(paths)
    decoded = unquote(name)
    if kind == "mockups":
        path = safe_join(paths["mockups"], decoded)
    elif kind == "inputs":
        path = safe_join(paths["inputs"], decoded)
    else:
        path = safe_join(paths["outputs"], decoded)
    if path.exists():
        path.unlink()
    return {"ok": True}


@app.delete("/api/assets/outputs-file/{file_path:path}")
def delete_output_file(ws: WorkspaceUser, file_path: str):
    ensure_dirs()
    paths = workspace_paths(ws)
    ensure_workspace_tree(paths)
    path = safe_join(paths["outputs"], unquote(file_path))
    if path.exists() and path.is_file():
        path.unlink()
    return {"ok": True}


@app.delete("/api/outputs/folder/{folder_name}")
def delete_output_folder(ws: WorkspaceUser, folder_name: str):
    ensure_dirs()
    paths = workspace_paths(ws)
    ensure_workspace_tree(paths)
    safe_folder = safe_name(unquote(folder_name))
    folder_path = safe_join(paths["outputs"], safe_folder)
    if folder_path.exists() and folder_path.is_dir():
        shutil.rmtree(folder_path)
    return {"ok": True}


@app.delete("/api/assets/{kind}")
def clear_assets(ws: WorkspaceUser, kind: Literal["mockups", "inputs", "outputs"]):
    ensure_dirs()
    paths = workspace_paths(ws)
    ensure_workspace_tree(paths)
    target = {"mockups": paths["mockups"], "inputs": paths["inputs"], "outputs": paths["outputs"]}[kind]
    clear_folder(target)
    return {"ok": True}


@app.post("/api/assets/{kind}/{name}/rename")
def rename_asset(ws: WorkspaceUser, kind: Literal["mockups", "inputs"], name: str, payload: RenamePayload):
    ensure_dirs()
    paths = workspace_paths(ws)
    ensure_workspace_tree(paths)
    decoded = unquote(name)
    src_base = paths["mockups"] if kind == "mockups" else paths["inputs"]
    src = safe_join(src_base, decoded)
    if not src.exists():
        raise HTTPException(status_code=404, detail="File not found.")
    new_name = safe_name(payload.new_name)
    dst = safe_join(src_base, new_name)
    if dst.exists() and dst != src:
        raise HTTPException(status_code=409, detail="Target file already exists.")
    src.rename(dst)
    return {"ok": True, "new_name": new_name}


@app.get("/api/templates")
def get_templates(ws: WorkspaceUser):
    return {"templates": read_user_templates(ws)}


@app.post("/api/templates")
def save_templates(ws: WorkspaceUser, payload: TemplatesPayload):
    write_user_templates(ws, payload.templates)
    return {"ok": True}


def _rel_env_path(p: Path) -> str:
    """Paths for script.py / subprocess cwd; use absolute if outside BASE_DIR (e.g. Local AppData)."""
    resolved = p.resolve()
    base = BASE_DIR.resolve()
    try:
        return resolved.relative_to(base).as_posix()
    except ValueError:
        return str(resolved)


def _run_script_inprocess(paths: dict[str, Path]) -> str:
    """
    Desktop/package mode: run generation in-process (no subprocess/script.py path issues).
    """
    old_input = script.INPUT_FOLDER
    old_output = script.OUTPUT_FOLDER
    old_mockups = script.MOCKUPS_FOLDER
    old_template = script.TEMPLATE_CONFIG_PATH
    try:
        script.INPUT_FOLDER = _rel_env_path(paths["inputs"])
        script.OUTPUT_FOLDER = _rel_env_path(paths["outputs"])
        script.MOCKUPS_FOLDER = _rel_env_path(paths["mockups"])
        script.TEMPLATE_CONFIG_PATH = _rel_env_path(paths["template_config"])

        buf = StringIO()
        with redirect_stdout(buf):
            script.main()
        return buf.getvalue()
    finally:
        script.INPUT_FOLDER = old_input
        script.OUTPUT_FOLDER = old_output
        script.MOCKUPS_FOLDER = old_mockups
        script.TEMPLATE_CONFIG_PATH = old_template


@app.post("/api/generate")
def generate(ws: WorkspaceUser, payload: GeneratePayload | None = None):
    ensure_dirs()
    print(f"[generate] start user={ws}", flush=True)
    if payload is None or payload.templates is None:
        raise HTTPException(status_code=400, detail="Templates are required in generate payload.")
    if not isinstance(payload.templates, list) or len(payload.templates) == 0:
        raise HTTPException(status_code=400, detail="Templates payload must be a non-empty array.")

    paths = workspace_paths(ws)
    ensure_workspace_tree(paths)

    # Always use templates provided by frontend for this run.
    write_user_templates(ws, payload.templates)
    # If frontend uploaded mockups to temp area, use those for this run.
    temp_has_mockups = any(
        file.is_file() and file.suffix.lower() in IMAGE_SUFFIXES
        for file in paths["temp_mockups"].iterdir()
    )
    print(f"[generate] temp_has_mockups={temp_has_mockups}", flush=True)
    if temp_has_mockups:
        copy_images(paths["temp_mockups"], paths["mockups"])
    temp_has_inputs = any(
        file.is_file() and file.suffix.lower() in IMAGE_SUFFIXES
        for file in paths["temp_inputs"].iterdir()
    )
    print(f"[generate] temp_has_inputs={temp_has_inputs}", flush=True)
    if temp_has_inputs:
        copy_images(paths["temp_inputs"], paths["inputs"])

    # Use in-process mode for packaged desktop binary, optional opt-in via env for constrained hosts.
    run_inprocess = getattr(sys, "frozen", False) or os.getenv("MOCKGENERATOR_RUN_INPROCESS") == "1"
    if run_inprocess:
        try:
            print("[generate] running script.py in-process ...", flush=True)
            out = _run_script_inprocess(paths)
        except Exception as exc:
            raise HTTPException(
                status_code=500,
                detail={
                    "message": "Generation failed.",
                    "stdout": "",
                    "stderr": str(exc),
                },
            ) from exc
    else:
        gen_env = os.environ.copy()
        gen_env["MOCKGENERATOR_INPUT_FOLDER"] = _rel_env_path(paths["inputs"])
        gen_env["MOCKGENERATOR_OUTPUT_FOLDER"] = _rel_env_path(paths["outputs"])
        gen_env["MOCKGENERATOR_MOCKUPS_FOLDER"] = _rel_env_path(paths["mockups"])
        gen_env["MOCKGENERATOR_TEMPLATE_CONFIG"] = _rel_env_path(paths["template_config"])

        print("[generate] running script.py ...", flush=True)
        process = subprocess.run(
            [sys.executable, "script.py"],
            cwd=str(BASE_DIR),
            capture_output=True,
            text=True,
            env=gen_env,
        )
        print(f"[generate] script returncode={process.returncode}", flush=True)
        if process.returncode != 0:
            print(
                "[generate] script stderr snippet:\n"
                + "\n".join(process.stderr.splitlines()[:40]),
                flush=True,
            )
            raise HTTPException(
                status_code=500,
                detail={
                    "message": "Generation failed.",
                    "stdout": process.stdout,
                    "stderr": process.stderr,
                },
            )
        out = process.stdout
    print("[generate] success", flush=True)
    return {"ok": True, "stdout": out}


@app.get("/api/files/mockups/{name}")
def file_mockup(ws: WorkspaceUser, name: str):
    paths = workspace_paths(ws)
    ensure_workspace_tree(paths)
    path = safe_join(paths["mockups"], unquote(name))
    if not path.exists():
        raise HTTPException(status_code=404, detail="File not found.")
    return FileResponse(path)


@app.get("/api/files/inputs/{name}")
def file_input(ws: WorkspaceUser, name: str):
    paths = workspace_paths(ws)
    ensure_workspace_tree(paths)
    path = safe_join(paths["inputs"], unquote(name))
    if not path.exists():
        raise HTTPException(status_code=404, detail="File not found.")
    return FileResponse(path)


@app.get("/api/files/output/{file_path:path}")
def file_output(ws: WorkspaceUser, file_path: str):
    paths = workspace_paths(ws)
    ensure_workspace_tree(paths)
    path = safe_join(paths["outputs"], unquote(file_path))
    if not path.exists():
        raise HTTPException(status_code=404, detail="File not found.")
    return FileResponse(path)


@app.get("/api/download/outputs")
def download_outputs(ws: WorkspaceUser):
    ensure_dirs()
    paths = workspace_paths(ws)
    ensure_workspace_tree(paths)
    tmp_dir = Path(tempfile.mkdtemp(prefix="mockgen-"))
    archive_base = tmp_dir / "outputs"
    archive_path = shutil.make_archive(str(archive_base), "zip", root_dir=str(paths["outputs"]))
    return FileResponse(
        archive_path,
        media_type="application/zip",
        filename="outputs.zip",
    )


@app.get("/api/download/output-file/{file_path:path}")
def download_output_file(ws: WorkspaceUser, file_path: str):
    ensure_dirs()
    paths = workspace_paths(ws)
    ensure_workspace_tree(paths)
    path = safe_join(paths["outputs"], unquote(file_path))
    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail="File not found.")
    return FileResponse(
        path,
        media_type="application/octet-stream",
        filename=path.name,
    )


@app.get("/api/download/output-folder/{folder_name}")
def download_output_folder(ws: WorkspaceUser, folder_name: str):
    ensure_dirs()
    paths = workspace_paths(ws)
    ensure_workspace_tree(paths)
    safe_folder = safe_name(unquote(folder_name))
    folder_path = safe_join(paths["outputs"], safe_folder)
    if not folder_path.exists() or not folder_path.is_dir():
        raise HTTPException(status_code=404, detail="Output folder not found.")

    tmp_dir = Path(tempfile.mkdtemp(prefix="mockgen-folder-"))
    archive_base = tmp_dir / safe_folder
    archive_path = shutil.make_archive(str(archive_base), "zip", root_dir=str(folder_path))
    return FileResponse(
        archive_path,
        media_type="application/zip",
        filename=f"{safe_folder}.zip",
    )


@app.get("/{full_path:path}")
def frontend_spa_fallback(full_path: str):
    if full_path.startswith("api/") or full_path in {"docs", "redoc", "openapi.json"}:
        raise HTTPException(status_code=404, detail="Not found.")
    return _frontend_file_or_index(full_path)

