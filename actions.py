# actions.py
import os

# actions.py
import os

from paramiko import SFTPClient

def list_local(path="."):
    entries = []
    try:
        for entry in os.scandir(path):
            try:
                entries.append({
                    "name": entry.name,
                    "is_dir": entry.is_dir(follow_symlinks=False),
                    "size": entry.stat().st_size if entry.is_file() else None,
                    "locked": False
                })
            except PermissionError:
                # Can see entry name, but not its details
                entries.append({
                    "name": entry.name,
                    "is_dir": True,   # usually dirs cause this
                    "size": None,
                    "locked": True
                })
    except PermissionError:
        # Whole folder is off-limits (like System Volume Information)
        print(f"[WARN] Access denied: {path}")
        return [{
            "name": os.path.basename(path),
            "is_dir": True,
            "size": None,
            "locked": True
        }]
    return entries


def list_remote(sftp, path="."):
    """List files in a remote directory via SFTP."""
    entries = []
    for attr in sftp.listdir_attr(path):
        entries.append({
            "name": attr.filename,
            "is_dir": bool(attr.st_mode & 0o40000),
            "size": attr.st_size if not (attr.st_mode & 0o40000) else None
        })
    return entries

progress_store = {}

def upload_file(sftp: SFTPClient, local_path: str, remote_path: str, transfer_id: str):
    file_size = os.path.getsize(local_path)
    progress_store[transfer_id] = {"done": 0, "total": file_size}

    def callback(transferred, total):
        progress_store[transfer_id] = {"done": transferred, "total": total}

    sftp.put(local_path, remote_path, callback=callback)

def download_file(sftp: SFTPClient, remote_path: str, local_path: str, transfer_id: str):
    file_size = sftp.stat(remote_path).st_size
    progress_store[transfer_id] = {"done": 0, "total": file_size}

    def callback(transferred, total):
        progress_store[transfer_id] = {"done": transferred, "total": total}

    sftp.get(remote_path, local_path, callback=callback)

def upload_dir(sftp, local_dir, remote_dir):
    """Recursively upload a directory to remote."""
    for root, dirs, files in os.walk(local_dir):
        rel_path = os.path.relpath(root, local_dir)
        target_dir = os.path.join(remote_dir, rel_path).replace("\\", "/")

        try:
            sftp.mkdir(target_dir)
        except IOError:
            pass  # directory may already exist

        for file in files:
            local_file = os.path.join(root, file)
            remote_file = os.path.join(target_dir, file).replace("\\", "/")
            upload_file(sftp, local_file, remote_file)

def download_dir(sftp, remote_dir, local_dir):
    """Recursively download a directory from remote."""
    os.makedirs(local_dir, exist_ok=True)

    for item in sftp.listdir_attr(remote_dir):
        remote_path = os.path.join(remote_dir, item.filename).replace("\\", "/")
        local_path = os.path.join(local_dir, item.filename)

        if bool(item.st_mode & 0o40000):  # is a directory
            download_dir(sftp, remote_path, local_path)
        else:
            download_file(sftp, remote_path, local_path)
