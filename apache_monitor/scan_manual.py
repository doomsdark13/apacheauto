# apache_monitor/scan_manual.py
import os
from .db import get_baseline, log_fs_event
from .utils import sha256sum

def manual_scan(target_dir):
    baseline = get_baseline()
    current_paths = set()
    new_files = 0
    modified_files = 0
    new_dirs = 0
    modified_dirs = 0
    changed_dirs = {}  # nama folder -> status

    # Walk current filesystem
    for dirpath, dirnames, filenames in os.walk(target_dir, followlinks=False):
        rel_dir = os.path.relpath(dirpath, target_dir)
        if rel_dir == ".":
            rel_dir = ""
        current_paths.add(rel_dir)

        # Cek folder
        mtime = os.path.getmtime(dirpath)
        key = rel_dir or "."
        if key not in baseline:
            new_dirs += 1
            changed_dirs[rel_dir or "root"] = "baru"
        else:
            if baseline[key]["mtime"] != mtime:
                modified_dirs += 1
                changed_dirs[rel_dir or "root"] = "diedit"

        # Cek file
        for f in filenames:
            filepath = os.path.join(dirpath, f)
            rel_path = os.path.relpath(filepath, target_dir)
            current_paths.add(rel_path)
            try:
                stat = os.stat(filepath)
                checksum = sha256sum(filepath)
                if rel_path not in baseline:
                    new_files += 1
                    # Simpan ke DB sebagai created
                    log_fs_event("created", rel_path, stat.st_size, stat.st_mtime, checksum)
                else:
                    old = baseline[rel_path]
                    if old["mtime"] != stat.st_mtime or old["checksum"] != checksum:
                        modified_files += 1
                        log_fs_event("modified", rel_path, stat.st_size, stat.st_mtime, checksum)
            except (OSError, IOError):
                continue

    # Hitung total
    total_files = len([p for p in current_paths if not p.endswith(os.sep) and p != "."])
    total_dirs = len([p for p in current_paths if p == "." or os.sep in p or p == ""])

    # Format daftar folder berubah
    folder_list = []
    for folder, status in changed_dirs.items():
        folder_list.append(f"  - {folder} ({status})")

    return {
        "total_files": total_files,
        "total_dirs": total_dirs,
        "new_files": new_files,
        "modified_files": modified_files,
        "changed_folders": folder_list
    }