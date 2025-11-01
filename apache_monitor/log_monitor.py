import re
import time
import os
from collections import defaultdict, deque
from datetime import datetime, timedelta
import threading
import queue
import logging

from .utils import now_str
from .db import log_ip_alert

logger = logging.getLogger("LogMonitor")

# Format log Apache combined
APACHE_COMBINED_REGEX = re.compile(
    r'(?P<ip>\S+) \S+ \S+ \[(?P<time>[^\]]+)\] "(?P<method>\S+) (?P<path>\S+) \S+" (?P<status>\d{3}) (?P<size>\S+) "(?P<referer>[^"]*)" "(?P<user_agent>[^"]*)"'
)

class LogMonitor:
    def __init__(self, config, alert_queue, dry_run=False):
        self.config = config
        self.alert_queue = alert_queue
        self.dry_run = dry_run
        self.ip_window = defaultdict(deque)  # IP -> deque of timestamps
        self.alerted_ips = {}  # IP -> last alert time
        self.file_inode = None
        self.file_offset = 0
        self.running = True

    def parse_line(self, line):
        match = APACHE_COMBINED_REGEX.match(line)
        if not match:
            return None
        data = match.groupdict()
        try:
            # Parse time: 01/Nov/2025:02:34:12 +0000
            log_time = datetime.strptime(data["time"].split()[0], "%d/%b/%Y:%H:%M:%S")
        except ValueError:
            log_time = datetime.utcnow()
        return {
            "ip": data["ip"],
            "path": data["path"],
            "user_agent": data["user_agent"],
            "timestamp": log_time,
            "raw": line.strip()
        }

    def is_suspicious_path(self, path):
        ext = os.path.splitext(path)[1].lower()
        if ext in self.config.get("suspicious_extensions", [".php", ".phar"]):
            return True
        for pattern in self.config.get("dangerous_patterns", []):
            if re.search(pattern, path):
                return True
        return False

    def check_threshold(self, ip, current_time):
        window = self.config["window_seconds"]
        threshold = self.config["threshold"]
        cutoff = current_time - timedelta(seconds=window)
        dq = self.ip_window[ip]

        # Hapus entri lama
        while dq and dq[0]["timestamp"] < cutoff:
            dq.popleft()

        if len(dq) >= threshold:
            # Cek cooldown
            last_alert = self.alerted_ips.get(ip)
            cooldown = self.config["alert_cooldown"]
            if not last_alert or (current_time - last_alert).total_seconds() > cooldown:
                paths = list(set(e["path"] for e in dq))
                example = dq[-1]["raw"]
                self.alerted_ips[ip] = current_time
                log_ip_alert(ip, len(dq), paths, example)
                logger.warning(f"[ALERT] Suspicious IP {ip} with {len(dq)} hits")
                self.alert_queue.put({
                    "type": "ip_alert",
                    "ip": ip,
                    "hits": len(dq),
                    "paths": paths[:3],
                    "example_path": paths[0] if paths else "",
                    "timestamp": now_str(),
                    "raw": example
                })
                return True
        return False

    def tail_file(self, filepath):
        """Tail file safely across rotation using inode tracking."""
        while self.running:
            try:
                if not os.path.exists(filepath):
                    time.sleep(1)
                    continue

                stat = os.stat(filepath)
                current_inode = stat.st_ino

                if self.file_inode != current_inode:
                    # File rotated or recreated
                    self.file_offset = 0
                    self.file_inode = current_inode

                with open(filepath, "r", encoding=self.config.get("log_encoding", "utf-8"), errors="replace") as f:
                    f.seek(self.file_offset)
                    while self.running:
                        line = f.readline()
                        if line:
                            self.file_offset = f.tell()
                            entry = self.parse_line(line)
                            if entry and self.is_suspicious_path(entry["path"]):
                                now = entry["timestamp"]
                                key = (entry["ip"], entry["user_agent"], entry["path"])
                                self.ip_window[entry["ip"]].append(entry)
                                self.check_threshold(entry["ip"], now)
                        else:
                            time.sleep(0.5)
            except (OSError, IOError) as e:
                logger.error(f"Error reading log file: {e}")
                time.sleep(2)

    def start(self):
        """Memulai log monitoring dengan validasi path"""
        log_path = self.config.get("target_log_path")
        
        if not log_path:
            logger.error("target_log_path tidak dikonfigurasi di config.yaml")
            raise ValueError("target_log_path tidak dikonfigurasi")
        
        # Validasi path (warning saja, karena file log mungkin belum ada saat startup)
        if not os.path.exists(log_path):
            logger.warning(f"File log tidak ditemukan: {log_path}")
            logger.info("Monitoring akan menunggu file log dibuat...")
        else:
            if not os.path.isfile(log_path):
                raise ValueError(f"target_log_path harus berupa file, bukan directory: {log_path}")
            if not os.access(log_path, os.R_OK):
                logger.warning(f"Tidak memiliki permission read untuk: {log_path}")
        
        logger.info(f"Memulai log monitoring untuk: {log_path}")
        thread = threading.Thread(target=self.tail_file, args=(log_path,), daemon=True)
        thread.start()
        return thread