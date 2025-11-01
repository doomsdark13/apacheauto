# apache_monitor/telegram_bot.py
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
import os
from .scan_manual import manual_scan
from .utils import sanitize_for_telegram

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
AUTHORIZED_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

async def test_scan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)
    if chat_id != AUTHORIZED_CHAT_ID:
        await update.message.reply_text("❌ Akses ditolak.")
        return

    from apache_monitor import config_loader  # akan kita buat
    config = config_loader.get_config()
    target_dir = config["target_dir"]

    try:
        result = manual_scan(target_dir)
        msg = (
            f"\\[TEST SCAN\\] Ringkasan Pemindaian Manual\n"
            f"📁 Total Folder: {result['total_dirs']}\n"
            f"📄 Total File: {result['total_files']}\n"
            f"➕ File Baru: {result['new_files']}\n"
            f"✏️ File Diedit: {result['modified_files']}\n"
        )
        if result["changed_folders"]:
            msg += "🆕 Folder Baru/Diedit:\n" + "\n".join(result["changed_folders"])
        else:
            msg += "🆕 Folder Baru/Diedit: -"

        await update.message.reply_text(sanitize_for_telegram(msg), parse_mode="MarkdownV2")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")

def start_bot():
    if not TELEGRAM_BOT_TOKEN or not AUTHORIZED_CHAT_ID:
        return None
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("test_scan", test_scan))
    return app