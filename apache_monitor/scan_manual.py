# apache_monitor/scan_manual.py
import os
import logging
from .db import get_baseline, log_fs_event
from .utils import sha256sum

logger = logging.getLogger("ScanManual")

def manual_scan(target_dir):
    """
    Melakukan scan manual filesystem dan membandingkan dengan baseline
    
    Args:
        target_dir: Directory yang akan di-scan
    
    Returns:
        Dictionary dengan hasil scan
    """
    if not os.path.exists(target_dir):
        raise ValueError(f"Directory tidak ditemukan: {target_dir}")
    
    if not os.path.isdir(target_dir):
        raise ValueError(f"Path bukan directory: {target_dir}")
    
    baseline = get_baseline()
    logger.info(f"Starting manual scan of: {target_dir}")
    
    total_files = 0
    total_dirs = 0
    new_files = 0
    modified_files = 0
    changed_dirs = {}  # rel_path -> status

    # Walk current filesystem
    try:
        for dirpath, dirnames, filenames in os.walk(target_dir, followlinks=False):
            try:
                rel_dir = os.path.relpath(dirpath, target_dir)
                if rel_dir == ".":
                    rel_dir = ""
                
                # Hitung directory
                total_dirs += 1

                # Cek folder
                try:
                    mtime = os.path.getmtime(dirpath)
                    key = rel_dir or "."
                    
                    if key not in baseline or baseline[key].get("is_dir") is False:
                        # Folder baru
                        changed_dirs[rel_dir or "root"] = "baru"
                    elif baseline[key].get("mtime") != mtime:
                        # Folder dimodifikasi
                        changed_dirs[rel_dir or "root"] = "diedit"
                except (OSError, IOError) as e:
                    logger.debug(f"Error checking directory {dirpath}: {e}")
                    continue

                # Cek file
                for f in filenames:
                    filepath = os.path.join(dirpath, f)
                    try:
                        rel_path = os.path.relpath(filepath, target_dir)
                        total_files += 1
                        
                        stat = os.stat(filepath)
                        checksum = sha256sum(filepath)
                        
                        if rel_path not in baseline:
                            # File baru
                            new_files += 1
                            log_fs_event("created", rel_path, stat.st_size, stat.st_mtime, checksum)
                        else:
                            # Cek apakah file berubah
                            old = baseline[rel_path]
                            if old.get("mtime") != stat.st_mtime or old.get("checksum") != checksum:
                                modified_files += 1
                                log_fs_event("modified", rel_path, stat.st_size, stat.st_mtime, checksum)
                    except (OSError, IOError, PermissionError) as e:
                        logger.debug(f"Error processing file {filepath}: {e}")
                        continue
                        
            except (OSError, PermissionError) as e:
                logger.warning(f"Error accessing directory {dirpath}: {e}")
                continue
    
    except Exception as e:
        logger.error(f"Error during filesystem walk: {e}", exc_info=True)
        raise

    # Format daftar folder berubah
    folder_list = []
    for folder, status in sorted(changed_dirs.items()):
        display_name = folder if folder != "root" else "(root)"
        folder_list.append(f"  • {display_name} ({status})")

    logger.info(f"Scan completed: {total_files} files, {total_dirs} dirs, {new_files} new, {modified_files} modified")
    
    return {
        "total_files": total_files,
        "total_dirs": total_dirs,
        "new_files": new_files,
        "modified_files": modified_files,
        "changed_folders": folder_list
    }