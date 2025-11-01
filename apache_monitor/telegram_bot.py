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
    
    logger.info(f"Received /test_scan from chat_id: {chat_id}")
    
    if chat_id != AUTHORIZED_CHAT_ID:
        logger.warning(f"Unauthorized access attempt from chat_id: {chat_id}")
        await update.message.reply_text("❌ Akses ditolak. Chat ID tidak terotorisasi.")
        return

    try:
        # Import dan load config
        from apache_monitor import config_loader
        config = config_loader.get_config()
        target_dir = config.get("target_dir")
        
        if not target_dir:
            await update.message.reply_text("❌ Error: target_dir tidak dikonfigurasi di config.yaml")
            return
        
        if not os.path.exists(target_dir):
            await update.message.reply_text(f"❌ Error: Directory tidak ditemukan: {target_dir}")
            return
        
        # Kirim pesan sedang memindai
        await update.message.reply_text("🔍 Memindai filesystem... Mohon tunggu...")
        
        # Jalankan scan
        result = manual_scan(target_dir)
        
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
        
        # Coba kirim dengan berbagai parse mode
        parse_modes = ["HTML", "MarkdownV2", None]
        
        for parse_mode in parse_modes:
            try:
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
                logger.info(f"Test scan result sent successfully using {parse_mode or 'plain'} mode")
                return
            except Exception as e:
                logger.debug(f"Failed to send with {parse_mode or 'plain'} mode: {e}")
                if parse_mode == parse_modes[-1]:  # Mode terakhir, raise error
                    raise
                continue
                
    except Exception as e:
        error_msg = f"❌ Error saat melakukan scan: {str(e)}"
        logger.error(f"Error in test_scan: {e}", exc_info=True)
        try:
            await update.message.reply_text(error_msg)
        except:
            # Jika gagal kirim error, log saja
            logger.error("Failed to send error message to Telegram")

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler untuk command /start"""
    await update.message.reply_text(
        "👋 ApacheAuto Monitor Bot\n\n"
        "Perintah yang tersedia:\n"
        "/test_scan - Lakukan scan manual filesystem"
    )

def start_bot():
    """Inisialisasi dan start Telegram bot"""
    if not TELEGRAM_BOT_TOKEN or not AUTHORIZED_CHAT_ID:
        logger.warning("TELEGRAM_BOT_TOKEN atau TELEGRAM_CHAT_ID tidak ditemukan")
        return None
    
    try:
        app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
        app.add_handler(CommandHandler("start", start_command))
        app.add_handler(CommandHandler("test_scan", test_scan))
        logger.info("Telegram bot initialized successfully")
        return app
    except Exception as e:
        logger.error(f"Failed to initialize Telegram bot: {e}")
        return None