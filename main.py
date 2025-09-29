import os
import shutil
import stat
import threading
import uuid

from fastapi.staticfiles import StaticFiles
import paramiko
import uvicorn
import webview
from fastapi import BackgroundTasks, FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from actions import download_dir, list_local, list_remote, progress_store, upload_dir
from helpers import recursive_rmdir
from read_yaml import get_config_values
from ssh_connection import create_connection


# --- FastAPI setup ---
app = FastAPI()
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")


# --- Global connection details ---
host, user, key_file, allow_recursive_delete = get_config_values("devices.yaml")
client, sftp, host, user, allow_recursive_delete = create_connection()



# --- Helpers ---
def run_sftp_task(func):
    """Helper to safely run a task with Paramiko SSH/SFTP."""
    with paramiko.SSHClient() as client:
        client.load_system_host_keys()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(hostname=host, username=user, key_filename=key_file)
        sftp = client.open_sftp()
        try:
            return func(sftp)
        finally:
            sftp.close()


def safe_filename(path: str) -> str:
    """If file exists, add suffix to avoid overwrite."""
    base, ext = os.path.splitext(path)
    counter = 1
    new_path = path
    while os.path.exists(new_path):
        new_path = f"{base}_{counter}{ext}"
        counter += 1
    return new_path


def sftp_safe_filename(sftp, path: str) -> str:
    """Remote-safe collision handler."""
    base, ext = os.path.splitext(path)
    counter = 1
    new_path = path
    try:
        while True:
            sftp.stat(new_path)  # will raise if file not found
            new_path = f"{base}_{counter}{ext}"
            counter += 1
    except IOError:
        return new_path


# --- Routes ---
@app.get("/", response_class=HTMLResponse)
async def index(
    request: Request,
    local_path: str = "C:/",
    remote_path: str = "."
):
    """Main index: list local + remote directories."""
    local_path = os.path.normpath(local_path)
    remote_path = os.path.normpath(remote_path)

    if os.path.splitdrive(local_path)[1] in ("", os.sep):
        local_path = "C:/"

    local_files = list_local(local_path)
    remote_files = list_remote(sftp, remote_path)

    return templates.TemplateResponse("index.html", {
        "request": request,
        "local_path": local_path.replace("\\", "/"),
        "remote_path": remote_path.replace("\\", "/"),
        "local_files": local_files,
        "remote_files": remote_files,
        "host": host,
        "user": user,
        "allow_recursive_delete": allow_recursive_delete
    })


@app.post("/upload")
async def upload_file(local_path: str = Form(...), remote_path: str = Form(...)):
    transfer_id = str(uuid.uuid4())
    progress_store[transfer_id] = {"done": 0, "total": 0, "status": "uploading"}

    def do_upload():
        def _task(sftp):
            if os.path.isdir(local_path):
                # folder upload
                upload_dir(sftp, local_path, remote_path, transfer_id_prefix=transfer_id)
            else:
                # single file upload
                target_path = sftp_safe_filename(sftp, remote_path)
                file_size = os.path.getsize(local_path)
                progress_store[transfer_id]["total"] = file_size

                def callback(transferred, total):
                    progress_store[transfer_id]["done"] = transferred
                    progress_store[transfer_id]["total"] = total

                sftp.put(local_path, target_path, callback=callback)

            progress_store[transfer_id]["status"] = "done"
            print(f"✅ Upload complete: {local_path} → {remote_path}")

        run_sftp_task(_task)

    threading.Thread(target=do_upload, daemon=True).start()
    return {"transfer_id": transfer_id}



@app.post("/download")
async def download_file(remote_path: str = Form(...), local_path: str = Form(...)):
    transfer_id = str(uuid.uuid4())
    progress_store[transfer_id] = {"done": 0, "total": 0, "status": "downloading"}

    def do_download():
        def _task(sftp):
            attr = sftp.stat(remote_path)
            if stat.S_ISDIR(attr.st_mode):
                # folder download
                download_dir(sftp, remote_path, local_path, transfer_id_prefix=transfer_id)
            else:
                # single file download
                target_path = safe_filename(local_path)
                file_size = attr.st_size
                progress_store[transfer_id]["total"] = file_size

                def callback(transferred, total):
                    progress_store[transfer_id]["done"] = transferred
                    progress_store[transfer_id]["total"] = total

                sftp.get(remote_path, target_path, callback=callback)

            progress_store[transfer_id]["status"] = "done"
            print(f"⬇️ Download complete: {remote_path} → {local_path}")

        run_sftp_task(_task)

    threading.Thread(target=do_download, daemon=True).start()
    return {"transfer_id": transfer_id}


@app.get("/progress/{transfer_id}")
async def progress(transfer_id: str):
    """
    Get current progress of a transfer.
    """
    return progress_store.get(transfer_id, {"done": 0, "total": 0, "status": "unknown"})

@app.post("/delete")
async def delete_file(path: str = Form(...)):
    def _task(sftp):
        try:
            attr = sftp.stat(path)
            if stat.S_ISDIR(attr.st_mode):
                if not allow_recursive_delete:
                    # Safe mode
                    sftp.rmdir(path)
                else:
                    # Recursive delete
                    recursive_rmdir(sftp, path)
            else:
                sftp.remove(path)
        except IOError as e:
            raise HTTPException(status_code=400, detail=str(e))

    run_sftp_task(_task)
    return {"status": "deleted"}



# --- Webview runner ---
def start_webview():
    webview.create_window("VoidSync", "http://127.0.0.1:8000", width=1200, height=800)
    webview.start()


if __name__ == "__main__":
    # Run FastAPI in background
    server_thread = threading.Thread(
        target=uvicorn.run,
        args=(app,),
        kwargs={"host": "127.0.0.1", "port": 8000, "log_level": "info"},
        daemon=True,
    )
    server_thread.start()

    # Launch PyWebView GUI
    try:
        start_webview()
    finally:
        sftp.close()
        client.close()
