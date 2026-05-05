import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal
from urllib.parse import quote, unquote

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

import script

BASE_DIR = Path(__file__).resolve().parent
MOCKUPS_DIR = BASE_DIR / "mockups"
INPUTS_DIR = BASE_DIR / "input_images"
OUTPUT_DIR = BASE_DIR / "output"
TEMPLATE_CONFIG_PATH = BASE_DIR / "template_config.json"
TEMP_ROOT_DIR = Path(tempfile.gettempdir()) / "mockgenerator"
TEMP_MOCKUPS_DIR = TEMP_ROOT_DIR / "mockups"
TEMP_INPUTS_DIR = TEMP_ROOT_DIR / "input_images"
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}


def ensure_dirs() -> None:
    MOCKUPS_DIR.mkdir(parents=True, exist_ok=True)
    INPUTS_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    TEMP_MOCKUPS_DIR.mkdir(parents=True, exist_ok=True)
    TEMP_INPUTS_DIR.mkdir(parents=True, exist_ok=True)


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


def list_outputs():
    files = []
    for file in sorted(OUTPUT_DIR.rglob("*")):
        if file.is_file() and file.suffix.lower() in IMAGE_SUFFIXES:
            rel = file.relative_to(OUTPUT_DIR).as_posix()
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


def read_templates():
    if TEMPLATE_CONFIG_PATH.exists():
        return json.loads(TEMPLATE_CONFIG_PATH.read_text(encoding="utf-8"))
    return script.DEFAULT_TEMPLATES


def write_templates(templates):
    TEMPLATE_CONFIG_PATH.write_text(json.dumps(templates, indent=2), encoding="utf-8")


class RenamePayload(BaseModel):
    new_name: str


class TemplatesPayload(BaseModel):
    templates: list


class GeneratePayload(BaseModel):
    templates: list | None = None


app = FastAPI(title="Mock Generator API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.getenv("FRONTEND_ORIGIN", "*")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    ensure_dirs()


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/assets")
def get_assets():
    ensure_dirs()
    return {
        "mockups": list_images(MOCKUPS_DIR, "/api/files/mockups/"),
        "inputs": list_images(INPUTS_DIR, "/api/files/inputs/"),
        "outputs": list_outputs(),
    }


@app.post("/api/upload/{kind}")
async def upload_files(kind: Literal["mockups", "inputs"], files: list[UploadFile] = File(...)):
    ensure_dirs()
    target = MOCKUPS_DIR if kind == "mockups" else INPUTS_DIR
    for uploaded in files:
        name = safe_name(uploaded.filename or "file.png")
        path = safe_join(target, name)
        content = await uploaded.read()
        path.write_bytes(content)
    return JSONResponse({"ok": True})


@app.post("/api/upload-temp/mockups")
async def upload_mockups_temp(files: list[UploadFile] = File(...)):
    ensure_dirs()
    clear_folder(TEMP_MOCKUPS_DIR)
    for uploaded in files:
        name = safe_name(uploaded.filename or "mockup.png")
        path = safe_join(TEMP_MOCKUPS_DIR, name)
        content = await uploaded.read()
        path.write_bytes(content)
    return JSONResponse({"ok": True})


@app.post("/api/upload-temp/inputs")
async def upload_inputs_temp(files: list[UploadFile] = File(...)):
    ensure_dirs()
    clear_folder(TEMP_INPUTS_DIR)
    for uploaded in files:
        name = safe_name(uploaded.filename or "input.png")
        path = safe_join(TEMP_INPUTS_DIR, name)
        content = await uploaded.read()
        path.write_bytes(content)
    return JSONResponse({"ok": True})


@app.delete("/api/assets/{kind}/{name}")
def delete_asset(kind: Literal["mockups", "inputs", "outputs"], name: str):
    ensure_dirs()
    decoded = unquote(name)
    if kind == "mockups":
        path = safe_join(MOCKUPS_DIR, decoded)
    elif kind == "inputs":
        path = safe_join(INPUTS_DIR, decoded)
    else:
        path = safe_join(OUTPUT_DIR, decoded)
    if path.exists():
        path.unlink()
    return {"ok": True}


@app.delete("/api/assets/outputs-file/{file_path:path}")
def delete_output_file(file_path: str):
    ensure_dirs()
    path = safe_join(OUTPUT_DIR, unquote(file_path))
    if path.exists() and path.is_file():
        path.unlink()
    return {"ok": True}


@app.delete("/api/outputs/folder/{folder_name}")
def delete_output_folder(folder_name: str):
    ensure_dirs()
    safe_folder = safe_name(unquote(folder_name))
    folder_path = safe_join(OUTPUT_DIR, safe_folder)
    if folder_path.exists() and folder_path.is_dir():
        shutil.rmtree(folder_path)
    return {"ok": True}


@app.delete("/api/assets/{kind}")
def clear_assets(kind: Literal["mockups", "inputs", "outputs"]):
    ensure_dirs()
    target = {"mockups": MOCKUPS_DIR, "inputs": INPUTS_DIR, "outputs": OUTPUT_DIR}[kind]
    clear_folder(target)
    return {"ok": True}


@app.post("/api/assets/{kind}/{name}/rename")
def rename_asset(kind: Literal["mockups", "inputs"], name: str, payload: RenamePayload):
    ensure_dirs()
    decoded = unquote(name)
    src_base = MOCKUPS_DIR if kind == "mockups" else INPUTS_DIR
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
def get_templates():
    return {"templates": read_templates()}


@app.post("/api/templates")
def save_templates(payload: TemplatesPayload):
    write_templates(payload.templates)
    return {"ok": True}


@app.post("/api/generate")
def generate(payload: GeneratePayload | None = None):
    ensure_dirs()
    if payload is None or payload.templates is None:
        raise HTTPException(status_code=400, detail="Templates are required in generate payload.")
    if not isinstance(payload.templates, list) or len(payload.templates) == 0:
        raise HTTPException(status_code=400, detail="Templates payload must be a non-empty array.")

    # Always use templates provided by frontend for this run.
    write_templates(payload.templates)
    # If frontend uploaded mockups to temp area, use those for this run.
    temp_has_mockups = any(
        file.is_file() and file.suffix.lower() in IMAGE_SUFFIXES
        for file in TEMP_MOCKUPS_DIR.iterdir()
    )
    if temp_has_mockups:
        copy_images(TEMP_MOCKUPS_DIR, MOCKUPS_DIR)
    temp_has_inputs = any(
        file.is_file() and file.suffix.lower() in IMAGE_SUFFIXES
        for file in TEMP_INPUTS_DIR.iterdir()
    )
    if temp_has_inputs:
        copy_images(TEMP_INPUTS_DIR, INPUTS_DIR)

    process = subprocess.run(
        [sys.executable, "script.py"],
        cwd=str(BASE_DIR),
        capture_output=True,
        text=True,
    )
    if process.returncode != 0:
        raise HTTPException(
            status_code=500,
            detail={
                "message": "Generation failed.",
                "stdout": process.stdout,
                "stderr": process.stderr,
            },
        )
    return {"ok": True, "stdout": process.stdout}


@app.get("/api/files/mockups/{name}")
def file_mockup(name: str):
    path = safe_join(MOCKUPS_DIR, unquote(name))
    if not path.exists():
        raise HTTPException(status_code=404, detail="File not found.")
    return FileResponse(path)


@app.get("/api/files/inputs/{name}")
def file_input(name: str):
    path = safe_join(INPUTS_DIR, unquote(name))
    if not path.exists():
        raise HTTPException(status_code=404, detail="File not found.")
    return FileResponse(path)


@app.get("/api/files/output/{file_path:path}")
def file_output(file_path: str):
    path = safe_join(OUTPUT_DIR, unquote(file_path))
    if not path.exists():
        raise HTTPException(status_code=404, detail="File not found.")
    return FileResponse(path)


@app.get("/api/download/outputs")
def download_outputs():
    ensure_dirs()
    tmp_dir = Path(tempfile.mkdtemp(prefix="mockgen-"))
    archive_base = tmp_dir / "outputs"
    archive_path = shutil.make_archive(str(archive_base), "zip", root_dir=str(OUTPUT_DIR))
    return FileResponse(
        archive_path,
        media_type="application/zip",
        filename="outputs.zip",
    )


@app.get("/api/download/output-file/{file_path:path}")
def download_output_file(file_path: str):
    ensure_dirs()
    path = safe_join(OUTPUT_DIR, unquote(file_path))
    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail="File not found.")
    return FileResponse(
        path,
        media_type="application/octet-stream",
        filename=path.name,
    )


@app.get("/api/download/output-folder/{folder_name}")
def download_output_folder(folder_name: str):
    ensure_dirs()
    safe_folder = safe_name(unquote(folder_name))
    folder_path = safe_join(OUTPUT_DIR, safe_folder)
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

