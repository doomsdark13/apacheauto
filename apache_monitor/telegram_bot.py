# apache_monitor/telegram_bot.py
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
import os
import logging
from .scan_manual import manual_scan
from .utils import sanitize_for_telegram

logger = logging.getLogger("TelegramBot")

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
AUTHORIZED_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

async def test_scan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler untuk command /test_scan"""
    chat_id = str(update.effective_chat.id)
    
    logger.info(f"Received /test_scan from chat_id: {chat_id}, authorized: {AUTHORIZED_CHAT_ID}")
    
    # Validasi authorized chat
    if chat_id != AUTHORIZED_CHAT_ID:
        logger.warning(f"Unauthorized access attempt from chat_id: {chat_id}")
        try:
            await update.message.reply_text("❌ Akses ditolak. Chat ID tidak terotorisasi.")
        except Exception as e:
            logger.error(f"Failed to send unauthorized message: {e}")
        return

    try:
        logger.info("Loading config...")
        # Import dan load config
        from apache_monitor import config_loader
        config = config_loader.get_config()
        logger.info(f"Config loaded: {list(config.keys())}")
        
        target_dir = config.get("target_dir")
        logger.info(f"Target directory: {target_dir}")
        
        if not target_dir:
            logger.error("target_dir tidak ditemukan di config")
            await update.message.reply_text("❌ Error: target_dir tidak dikonfigurasi di config.yaml")
            return
        
        if not os.path.exists(target_dir):
            logger.error(f"Directory tidak ditemukan: {target_dir}")
            await update.message.reply_text(f"❌ Error: Directory tidak ditemukan: {target_dir}")
            return
        
        # Kirim pesan sedang memindai
        logger.info("Sending scan started message...")
        try:
            await update.message.reply_text("🔍 Memindai filesystem... Mohon tunggu...")
        except Exception as e:
            logger.error(f"Failed to send scan started message: {e}")
            # Continue anyway
        
        # Jalankan scan
        logger.info(f"Starting manual scan of: {target_dir}")
        result = manual_scan(target_dir)
        logger.info(f"Scan completed: {result}")
        
        # Format pesan tanpa escape manual - akan di-sanitize nanti
        msg = (
            f"✅ [TEST SCAN] Ringkasan Pemindaian Manual\n"
            f"📁 Total Folder: {result.get('total_dirs', 0)}\n"
            f"📄 Total File: {result.get('total_files', 0)}\n"
            f"➕ File Baru: {result.get('new_files', 0)}\n"
            f"✏️ File Diedit: {result.get('modified_files', 0)}\n"
        )
        
        changed_folders = result.get("changed_folders", [])
        if changed_folders:
            msg += "\n🆕 Folder Baru/Diedit:\n"
            # Batasi hanya 10 folder pertama untuk menghindari pesan terlalu panjang
            for folder in changed_folders[:10]:
                msg += f"{folder}\n"
            if len(changed_folders) > 10:
                msg += f"\n... dan {len(changed_folders) - 10} folder lainnya"
        else:
            msg += "\n🆕 Folder Baru/Diedit: Tidak ada perubahan"
        
        logger.info(f"Formatted message length: {len(msg)} characters")
        
        # Coba kirim dengan berbagai parse mode
        parse_modes = ["HTML", "MarkdownV2", None]
        
        last_error = None
        for parse_mode in parse_modes:
            try:
                logger.info(f"Trying to send with parse_mode: {parse_mode}")
                if parse_mode == "MarkdownV2":
                    text = sanitize_for_telegram(msg)
                elif parse_mode == "HTML":
                    text = msg.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                else:
                    text = msg
                
                await update.message.reply_text(
                    text,
                    parse_mode=parse_mode
                )
                logger.info(f"✅ Test scan result sent successfully using {parse_mode or 'plain'} mode")
                return
            except Exception as e:
                last_error = str(e)
                logger.warning(f"❌ Failed to send with {parse_mode or 'plain'} mode: {e}")
                if parse_mode == parse_modes[-1]:  # Mode terakhir
                    # Akan di-handle di outer exception handler
                    raise
                continue
                
    except Exception as e:
        error_msg = f"❌ Error saat melakukan scan:\n{str(e)}"
        logger.error(f"Error in test_scan: {e}", exc_info=True)
        try:
            # Coba kirim error dengan plain text
            await update.message.reply_text(error_msg, parse_mode=None)
            logger.info("Error message sent to user")
        except Exception as send_error:
            logger.error(f"Failed to send error message to Telegram: {send_error}")
            # Coba sekali lagi tanpa parse mode
            try:
                await update.message.reply_text(f"Error: {str(e)[:400]}")  # Batasi panjang
            except:
                logger.error("Completely failed to send any message to Telegram")

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler untuk command /start"""
    await update.message.reply_text(
        "👋 ApacheAuto Monitor Bot\n\n"
        "Perintah yang tersedia:\n"
        "/test_scan - Lakukan scan manual filesystem"
    )

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle errors in telegram bot"""
    logger.error(f"Exception while handling an update: {context.error}", exc_info=context.error)
    
    # Try to send error message to user if update exists
    if update and hasattr(update, 'effective_chat') and update.effective_chat:
        try:
            error_msg = f"❌ Terjadi error: {str(context.error)[:200]}"
            if hasattr(update, 'message') and update.message:
                await update.message.reply_text(error_msg)
            elif hasattr(update, 'callback_query') and update.callback_query:
                await update.callback_query.message.reply_text(error_msg)
        except Exception as e:
            logger.error(f"Failed to send error message: {e}")

def start_bot():
    """Inisialisasi dan start Telegram bot"""
    if not TELEGRAM_BOT_TOKEN or not AUTHORIZED_CHAT_ID:
        logger.warning("TELEGRAM_BOT_TOKEN atau TELEGRAM_CHAT_ID tidak ditemukan")
        logger.warning(f"TELEGRAM_BOT_TOKEN: {'SET' if TELEGRAM_BOT_TOKEN else 'NOT SET'}")
        logger.warning(f"TELEGRAM_CHAT_ID: {'SET' if AUTHORIZED_CHAT_ID else 'NOT SET'}")
        return None
    
    try:
        logger.info("Initializing Telegram bot...")
        app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
        
        # Add error handler
        app.add_error_handler(error_handler)
        
        # Add command handlers
        app.add_handler(CommandHandler("start", start_command))
        app.add_handler(CommandHandler("test_scan", test_scan))
        
        logger.info(f"Telegram bot initialized successfully for chat_id: {AUTHORIZED_CHAT_ID}")
        return app
    except Exception as e:
        logger.error(f"Failed to initialize Telegram bot: {e}", exc_info=True)
        return None