import os
import time
import json
import requests
from queue import Queue, Empty
from .utils import sanitize_for_telegram
from .db import log_notification
import logging

logger = logging.getLogger("Notifier")

class Notifier:
    def __init__(self, config, alert_queue, dry_run=False):
        self.config = config
        self.alert_queue = alert_queue
        self.dry_run = dry_run
        self.token = os.getenv("TELEGRAM_BOT_TOKEN")
        self.chat_id = os.getenv("TELEGRAM_CHAT_ID")
        
        # Telegram opsional - hanya warning jika tidak ada
        if not self.token or not self.chat_id:
            logger.warning("TELEGRAM_BOT_TOKEN atau TELEGRAM_CHAT_ID tidak ditemukan di .env")
            logger.warning("Notifikasi Telegram tidak akan berfungsi. Fitur monitoring tetap berjalan.")
            self.token = None
            self.chat_id = None

    def send_telegram(self, message):
        if not self.token or not self.chat_id:
            logger.debug("Telegram tidak dikonfigurasi, skip sending")
            return False
            
        if self.dry_run:
            logger.info(f"[DRY-RUN] Telegram message: {message}")
            return True

        url = f"https://api.telegram.org/bot{self.token}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": sanitize_for_telegram(message),
            "parse_mode": "MarkdownV2"
        }
        for attempt in range(3):
            try:
                resp = requests.post(url, json=payload, timeout=10)
                if resp.status_code == 200:
                    log_notification("telegram", message)
                    return True
                else:
                    logger.warning(f"Telegram failed: {resp.status_code} {resp.text}")
            except Exception as e:
                logger.error(f"Telegram error: {e}")
            time.sleep(2 ** attempt)  # exponential backoff
        return False

    def format_alert(self, event):
        if event["type"] == "ip_alert":
            msg = (
                f"\\[ALERT\\] Brute\\-like access detected\n"
                f"IP: {event['ip']}\n"
                f"Hits: {event['hits']} dalam {self.config['window_seconds']}s\n"
                f"Contoh path: {event['example_path']}\n"
                f"Time: {event['timestamp']}"
            )
            return msg
        elif event["type"] == "fs_alert":
            msg = (
                f"\\[FS ALERT\\] File berbahaya terdeteksi\n"
                f"Event: {event['event']}\n"
                f"Path: {event['path']}\n"
                f"Size: {event['size']} bytes\n"
                f"Time: {event['timestamp']}"
            )
            return msg
        return None

    def run(self):
        """Loop utama untuk memproses alert queue"""
        logger.info("Notifier siap memproses alert...")
        if not self.token or not self.chat_id:
            logger.warning("Notifier berjalan TANPA Telegram. Alert hanya akan dicatat di database.")
        
        while True:
            try:
                # Timeout adalah kondisi normal jika queue kosong
                event = self.alert_queue.get(timeout=1)
                msg = self.format_alert(event)
                if msg:
                    success = self.send_telegram(msg)
                    if not success and (self.token and self.chat_id):
                        logger.warning("Gagal mengirim notifikasi Telegram, namun alert tetap tercatat di database")
                else:
                    logger.warning(f"Tidak dapat memformat alert untuk event: {event.get('type', 'unknown')}")
                self.alert_queue.task_done()
            except Empty:
                # Queue kosong setelah timeout - ini kondisi normal, lanjutkan loop
                continue
            except Exception as e:
                logger.error(f"Error memproses alert queue: {e}", exc_info=True)
                continue