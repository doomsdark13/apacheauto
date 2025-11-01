# Apakah kode ini sudah berjalan sebagaimana mestinya?
# Berikut adalah pemeriksaan menyeluruh beserta saran jika ada:

import os
import sys
import argparse
import logging
import logging.handlers
from queue import Queue
from dotenv import load_dotenv
import yaml

from apache_monitor.db import init_db
from apache_monitor.log_monitor import LogMonitor
from apache_monitor.fs_monitor import FsMonitor
from apache_monitor.notifier import Notifier

# Perlu impor start_bot agar telegram_app bisa diinisialisasi
try:
    from apache_monitor.telegram_bot import start_bot
except ImportError:
    start_bot = None

def setup_logging():
    os.makedirs("logs", exist_ok=True)
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    handler = logging.handlers.TimedRotatingFileHandler(
        "logs/system.log", when="midnight", interval=1, backupCount=7
    )
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    console = logging.StreamHandler()
    console.setFormatter(formatter)
    logger.addHandler(console)
    return logger

def load_config(config_path="config.yaml"):
    with open(config_path) as f:
        return yaml.safe_load(f)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Do not send Telegram alerts")
    parser.add_argument("--once", action="store_true", help="Scan log once and exit (not implemented fully)")
    args = parser.parse_args()

    load_dotenv()
    logger = setup_logging()
    init_db()

    config = load_config()
    alert_queue = Queue()

    try:
        # Validasi konfigurasi dasar
        required_keys = ["target_log_path", "target_dir", "threshold", "window_seconds"]
        missing_keys = [key for key in required_keys if key not in config]
        if missing_keys:
            logger.error(f"Konfigurasi tidak lengkap. Key yang hilang: {missing_keys}")
            logger.error("Pastikan config.yaml berisi semua key yang diperlukan.")
            sys.exit(1)
        
        # Start components
        log_mon = LogMonitor(config, alert_queue, dry_run=args.dry_run)
        fs_mon = FsMonitor(config, alert_queue, dry_run=args.dry_run)
        notifier = Notifier(config, alert_queue, dry_run=args.dry_run)

        # Jalankan Telegram bot (jika token tersedia dan start_bot bisa diimport)
        telegram_app = start_bot() if start_bot else None
        if telegram_app:
            import threading
            import time
            
            def run_telegram_bot():
                try:
                    logger.info("Starting Telegram bot polling...")
                    telegram_app.run_polling(
                        allowed_updates=["message", "callback_query"],
                        drop_pending_updates=True
                    )
                except Exception as e:
                    logger.error(f"Error in Telegram bot polling: {e}", exc_info=True)
            
            tg_thread = threading.Thread(target=run_telegram_bot, daemon=True, name="TelegramBot")
            tg_thread.start()
            
            # Beri waktu untuk bot mulai
            time.sleep(2)
            
            if tg_thread.is_alive():
                logger.info("✅ Telegram bot listener started successfully for /test_scan")
            else:
                logger.warning("⚠️ Telegram bot thread tidak berjalan")
        else:
            logger.warning("Telegram bot tidak diinisialisasi (token atau chat_id tidak ada)")

        # Start monitors dengan error handling terpisah
        log_thread = None
        fs_observer = None
        
        try:
            log_thread = log_mon.start()
            logger.info("Log monitor berhasil dimulai")
        except Exception as e:
            logger.error(f"Gagal memulai log monitor: {e}")
            if not args.dry_run:
                logger.error("Log monitoring diperlukan untuk aplikasi. Keluar...")
                sys.exit(1)
        
        try:
            fs_observer = fs_mon.start()
            logger.info("Filesystem monitor berhasil dimulai")
        except (FileNotFoundError, ValueError, PermissionError) as e:
            logger.error(f"Gagal memulai filesystem monitor: {e}")
            logger.warning("Aplikasi akan terus berjalan TANPA filesystem monitoring")
            fs_observer = None
        except Exception as e:
            logger.error(f"Error tidak terduga saat memulai filesystem monitor: {e}", exc_info=True)
            fs_observer = None

        if args.once:
            print("Once mode not fully implemented; exiting.")
            if fs_observer:
                fs_observer.stop()
                fs_observer.join()
            return 0

        logger.info("ApacheAuto Monitor berjalan. Tekan Ctrl+C untuk menghentikan.")
        notifier.run()  # blocks

    except KeyboardInterrupt:
        logger.info("\nMenerima signal interrupt, menghentikan monitor...")
        if 'fs_observer' in locals() and fs_observer:
            try:
                fs_observer.stop()
                fs_observer.join(timeout=5)
                logger.info("Filesystem observer dihentikan")
            except Exception as e:
                logger.warning(f"Error menghentikan filesystem observer: {e}")
        sys.exit(0)
    except Exception as e:
        # Tambahan untuk logging error yang tidak terduga
        logger.error(f"Unexpected error: {str(e)}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
# Kesimpulan:
# - Kode sudah cukup baik dan terstruktur.
# - Pastikan semua dependency, file config, dan environment variable ada.
# - Apabila start_bot tidak ditemukan/import error, kode akan tetap berjalan tanpa fitur Telegram.
# - Mode `--once` memang belum diimplementasikan sepenuhnya.