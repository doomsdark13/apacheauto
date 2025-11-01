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
        
        # Coba dengan berbagai parse mode: MarkdownV2 -> HTML -> Plain text
        parse_modes = [
            ("MarkdownV2", lambda msg: sanitize_for_telegram(msg)),
            ("HTML", lambda msg: self._escape_html(msg)),
            (None, lambda msg: msg)  # Plain text tanpa formatting
        ]
        
        last_error = None
        for parse_mode, escape_func in parse_modes:
            try:
                payload = {
                    "chat_id": self.chat_id,
                    "text": escape_func(message)
                }
                if parse_mode:
                    payload["parse_mode"] = parse_mode
                
                resp = requests.post(url, json=payload, timeout=10)
                resp_data = resp.json()
                
                if resp.status_code == 200 and resp_data.get("ok"):
                    log_notification("telegram", message)
                    if parse_mode != "MarkdownV2":
                        logger.info(f"Telegram message sent using {parse_mode or 'plain text'} mode")
                    return True
                elif resp.status_code == 400 and "can't parse entities" in resp_data.get("description", ""):
                    # Parse error - coba mode berikutnya
                    last_error = resp_data.get("description", "Parse error")
                    logger.debug(f"Parse mode {parse_mode} failed: {last_error}. Trying next mode...")
                    continue
                else:
                    # Error lainnya - log dan coba mode berikutnya sebagai fallback
                    last_error = resp_data.get("description", resp.text)
                    logger.warning(f"Telegram failed with {parse_mode or 'plain'} mode: {last_error}")
                    if parse_mode == parse_modes[-1][0]:  # Sudah mode terakhir
                        return False
                    continue
            except Exception as e:
                last_error = str(e)
                logger.error(f"Telegram error with {parse_mode or 'plain'} mode: {e}")
                if parse_mode == parse_modes[-1][0]:  # Sudah mode terakhir
                    return False
                continue
        
        logger.error(f"Failed to send Telegram message with all parse modes. Last error: {last_error}")
        return False
    
    def _escape_html(self, text):
        """Escape text untuk Telegram HTML mode"""
        if not isinstance(text, str):
            text = str(text)
        # HTML mode hanya perlu escape: < > &
        return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    def format_alert(self, event):
        """
        Format alert message. Jangan escape manual di sini,
        biarkan sanitize_for_telegram yang menangani escaping.
        """
        if event["type"] == "ip_alert":
            msg = (
                f"🔴 [ALERT] Brute-like access detected\n"
                f"📍 IP: {event.get('ip', 'N/A')}\n"
                f"🔢 Hits: {event.get('hits', 0)} dalam {self.config.get('window_seconds', 60)}s\n"
                f"📂 Path: {event.get('example_path', 'N/A')}\n"
                f"⏰ Time: {event.get('timestamp', 'N/A')}"
            )
            return msg
        elif event["type"] == "fs_alert":
            msg = (
                f"⚠️ [FS ALERT] File berbahaya terdeteksi\n"
                f"📝 Event: {event.get('event', 'N/A')}\n"
                f"📂 Path: {event.get('path', 'N/A')}\n"
                f"📊 Size: {event.get('size', 0)} bytes\n"
                f"⏰ Time: {event.get('timestamp', 'N/A')}"
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