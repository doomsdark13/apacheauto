import os
import time
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from .utils import sha256sum, sanitize_for_telegram
from .db import log_fs_event
import logging

logger = logging.getLogger("FsMonitor")

class FsEventHandler(FileSystemEventHandler):
    def __init__(self, alert_queue, target_dir, suspicious_exts):
        self.alert_queue = alert_queue
        self.target_dir = target_dir
        self.suspicious_exts = suspicious_exts

    def _is_high_priority(self, filepath):
        if not os.path.isfile(filepath):
            return False
        ext = os.path.splitext(filepath)[1].lower()
        return ext in self.suspicious_exts

    def _log_and_alert(self, event_type, src_path):
        rel_path = os.path.relpath(src_path, self.target_dir)
        size = 0
        mtime = 0
        checksum = None
        if os.path.exists(src_path):
            stat = os.stat(src_path)
            size = stat.st_size
            mtime = stat.st_mtime
            checksum = sha256sum(src_path)

        log_fs_event(event_type, rel_path, size, mtime, checksum)

        if self._is_high_priority(src_path):
            self.alert_queue.put({
                "type": "fs_alert",
                "event": event_type,
                "path": rel_path,
                "size": size,
                "checksum": checksum,
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
            })
            logger.warning(f"[FS ALERT] High-priority change: {event_type} {rel_path}")

    def on_created(self, event):
        if not event.is_directory:
            self._log_and_alert("created", event.src_path)

    def on_modified(self, event):
        if not event.is_directory:
            self._log_and_alert("modified", event.src_path)

    def on_deleted(self, event):
        if not event.is_directory:
            self._log_and_alert("deleted", event.src_path)

    def on_moved(self, event):
        if not event.is_directory:
            self._log_and_alert("renamed", event.dest_path)

class FsMonitor:
    def __init__(self, config, alert_queue, dry_run=False):
        self.config = config
        self.alert_queue = alert_queue
        self.dry_run = dry_run
        self.observer = Observer()
        self.target_dir = self.config.get("target_dir")

    def start(self):
        """Memulai filesystem monitoring dengan validasi path"""
        if not self.target_dir:
            logger.error("target_dir tidak dikonfigurasi di config.yaml")
            raise ValueError("target_dir tidak dikonfigurasi")
        
        # Validasi path
        if not os.path.exists(self.target_dir):
            logger.warning(f"Path target_dir tidak ditemukan: {self.target_dir}")
            logger.info("Mencoba membuat directory jika memungkinkan...")
            try:
                os.makedirs(self.target_dir, exist_ok=True)
                logger.info(f"Directory berhasil dibuat: {self.target_dir}")
            except (OSError, PermissionError) as e:
                logger.error(f"Tidak dapat membuat directory {self.target_dir}: {e}")
                logger.error("Filesystem monitoring TIDAK AKAN BERJALAN. Pastikan path valid dan memiliki permission yang cukup.")
                raise FileNotFoundError(f"Directory tidak ditemukan dan tidak dapat dibuat: {self.target_dir}") from e
        
        if not os.path.isdir(self.target_dir):
            raise ValueError(f"target_dir harus berupa directory, bukan file: {self.target_dir}")
        
        if not os.access(self.target_dir, os.R_OK):
            logger.warning(f"Tidak memiliki permission read untuk: {self.target_dir}")
        
        logger.info(f"Memulai filesystem monitoring untuk: {self.target_dir}")
        
        handler = FsEventHandler(
            self.alert_queue,
            self.target_dir,
            set(self.config.get("suspicious_extensions", [".php", ".phar"]))
        )
        self.observer.schedule(
            handler,
            self.target_dir,
            recursive=True
        )
        self.observer.start()
        logger.info("Filesystem observer berhasil dimulai")
        return self.observer