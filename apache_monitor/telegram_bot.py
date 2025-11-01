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
    
    print(f"\n[TELEGRAM BOT] Received /test_scan from chat_id: {chat_id}")
    print(f"[TELEGRAM BOT] Authorized chat_id: {AUTHORIZED_CHAT_ID}")
    logger.info(f"Received /test_scan from chat_id: {chat_id}, authorized: {AUTHORIZED_CHAT_ID}")
    
    # Validasi authorized chat
    if chat_id != AUTHORIZED_CHAT_ID:
        print(f"[TELEGRAM BOT] ⚠️ UNAUTHORIZED: chat_id {chat_id} tidak terotorisasi!")
        logger.warning(f"Unauthorized access attempt from chat_id: {chat_id}")
        try:
            await update.message.reply_text("❌ Akses ditolak. Chat ID tidak terotorisasi.")
        except Exception as e:
            print(f"[TELEGRAM BOT] ❌ ERROR: Failed to send unauthorized message: {e}")
            logger.error(f"Failed to send unauthorized message: {e}")
        return

    try:
        print("[TELEGRAM BOT] Loading config...")
        logger.info("Loading config...")
        # Import dan load config
        from apache_monitor import config_loader
        config = config_loader.get_config()
        print(f"[TELEGRAM BOT] Config loaded: {list(config.keys())}")
        logger.info(f"Config loaded: {list(config.keys())}")
        
        target_dir = config.get("target_dir")
        print(f"[TELEGRAM BOT] Target directory: {target_dir}")
        logger.info(f"Target directory: {target_dir}")
        
        if not target_dir:
            error_msg = "❌ Error: target_dir tidak dikonfigurasi di config.yaml"
            print(f"[TELEGRAM BOT] ❌ CONFIG ERROR: target_dir tidak ditemukan")
            logger.error("target_dir tidak ditemukan di config")
            await update.message.reply_text(error_msg, parse_mode=None)
            return
        
        if not os.path.exists(target_dir):
            error_msg = f"❌ Error: Directory tidak ditemukan: {target_dir}"
            print(f"[TELEGRAM BOT] ❌ PATH ERROR: Directory tidak ditemukan: {target_dir}")
            logger.error(f"Directory tidak ditemukan: {target_dir}")
            await update.message.reply_text(error_msg, parse_mode=None)
            return
        
        # Kirim pesan sedang memindai
        print("[TELEGRAM BOT] Sending scan started message...")
        logger.info("Sending scan started message...")
        try:
            await update.message.reply_text("🔍 Memindai filesystem... Mohon tunggu...", parse_mode=None)
            print("[TELEGRAM BOT] ✅ Scan started message sent")
        except Exception as e:
            print(f"[TELEGRAM BOT] ❌ ERROR: Failed to send scan started message: {e}")
            logger.error(f"Failed to send scan started message: {e}")
            # Continue anyway
        
        # Jalankan scan
        print(f"[TELEGRAM BOT] Starting manual scan of: {target_dir}")
        logger.info(f"Starting manual scan of: {target_dir}")
        try:
            result = manual_scan(target_dir)
            print(f"[TELEGRAM BOT] ✅ Scan completed: {result}")
            logger.info(f"Scan completed: {result}")
        except Exception as scan_error:
            print(f"[TELEGRAM BOT] ❌ SCAN ERROR: {scan_error}")
            logger.error(f"Error during scan: {scan_error}", exc_info=True)
            await update.message.reply_text(
                f"❌ Error saat scan:\n{str(scan_error)[:300]}",
                parse_mode=None
            )
            return
        
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
                print(f"[TELEGRAM BOT] Trying to send with parse_mode: {parse_mode}")
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
                print(f"[TELEGRAM BOT] ✅ Successfully sent scan result using {parse_mode or 'plain'} mode")
                logger.info(f"✅ Test scan result sent successfully using {parse_mode or 'plain'} mode")
                return
            except Exception as e:
                last_error = str(e)
                print(f"[TELEGRAM BOT] ❌ Failed with {parse_mode or 'plain'} mode: {e}")
                logger.warning(f"❌ Failed to send with {parse_mode or 'plain'} mode: {e}")
                if parse_mode == parse_modes[-1]:  # Mode terakhir
                    # Akan di-handle di outer exception handler
                    raise
                continue
                
    except Exception as e:
        error_msg = f"❌ Error saat melakukan scan:\n{str(e)[:400]}"
        print(f"[TELEGRAM BOT] ❌ CRITICAL ERROR in test_scan: {e}")
        print(f"[TELEGRAM BOT] Error type: {type(e).__name__}")
        logger.error(f"Error in test_scan: {e}", exc_info=True)
        try:
            # Coba kirim error dengan plain text
            await update.message.reply_text(error_msg, parse_mode=None)
            print(f"[TELEGRAM BOT] ✅ Error message sent to user")
            logger.info("Error message sent to user")
        except Exception as send_error:
            print(f"[TELEGRAM BOT] ❌ CRITICAL: Failed to send error message: {send_error}")
            logger.error(f"Failed to send error message to Telegram: {send_error}")
            # Coba sekali lagi tanpa parse mode
            try:
                await update.message.reply_text(f"Error: {str(e)[:400]}", parse_mode=None)
                print(f"[TELEGRAM BOT] ✅ Fallback error message sent")
            except Exception as final_error:
                print(f"[TELEGRAM BOT] ❌ COMPLETELY FAILED: Cannot send any message! {final_error}")
                logger.error("Completely failed to send any message to Telegram")

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler untuk command /start"""
    chat_id = str(update.effective_chat.id)
    
    # Log ke terminal
    print(f"\n[TELEGRAM BOT] Received /start command from chat_id: {chat_id}")
    logger.info(f"Received /start from chat_id: {chat_id}")
    
    try:
        msg = (
            "👋 ApacheAuto Monitor Bot\n\n"
            "Perintah yang tersedia:\n"
            "/start - Tampilkan menu ini\n"
            "/test_scan - Lakukan scan manual filesystem\n"
            "/test - Test koneksi bot (simple message)"
        )
        
        await update.message.reply_text(msg, parse_mode=None)
        print(f"[TELEGRAM BOT] ✅ Successfully sent /start response to chat_id: {chat_id}")
        logger.info("Successfully sent /start response")
        
    except Exception as e:
        error_msg = f"❌ Error sending /start response: {str(e)}"
        print(f"[TELEGRAM BOT] ❌ ERROR: {error_msg}")
        logger.error(f"Error in start_command: {e}", exc_info=True)
        
        # Coba kirim error message
        try:
            await update.message.reply_text(f"Error: {str(e)[:200]}", parse_mode=None)
        except:
            print(f"[TELEGRAM BOT] ❌ CRITICAL: Cannot send any message to Telegram!")
            logger.error("CRITICAL: Cannot send any message to Telegram")

async def test_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Simple test command untuk memastikan bot bisa kirim pesan"""
    chat_id = str(update.effective_chat.id)
    
    print(f"\n[TELEGRAM BOT] Received /test command from chat_id: {chat_id}")
    logger.info(f"Received /test from chat_id: {chat_id}")
    
    try:
        test_msg = "✅ Bot berfungsi dengan baik! Connection OK."
        await update.message.reply_text(test_msg, parse_mode=None)
        print(f"[TELEGRAM BOT] ✅ Successfully sent test message to chat_id: {chat_id}")
        logger.info("Successfully sent test message")
    except Exception as e:
        print(f"[TELEGRAM BOT] ❌ ERROR sending test message: {e}")
        print(f"[TELEGRAM BOT] Error details: {type(e).__name__}: {str(e)}")
        logger.error(f"Error in test_command: {e}", exc_info=True)

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle errors in telegram bot"""
    error = context.error
    print(f"\n[TELEGRAM BOT] ❌ ERROR HANDLER TRIGGERED!")
    print(f"[TELEGRAM BOT] Error type: {type(error).__name__}")
    print(f"[TELEGRAM BOT] Error message: {str(error)}")
    logger.error(f"Exception while handling an update: {error}", exc_info=error)
    
    # Try to send error message to user if update exists
    if update and hasattr(update, 'effective_chat') and update.effective_chat:
        try:
            error_msg = f"❌ Terjadi error: {str(error)[:200]}"
            if hasattr(update, 'message') and update.message:
                await update.message.reply_text(error_msg, parse_mode=None)
                print(f"[TELEGRAM BOT] ✅ Error message sent to user")
            elif hasattr(update, 'callback_query') and update.callback_query:
                await update.callback_query.message.reply_text(error_msg, parse_mode=None)
                print(f"[TELEGRAM BOT] ✅ Error message sent via callback")
        except Exception as e:
            print(f"[TELEGRAM BOT] ❌ CRITICAL: Failed to send error message: {e}")
            logger.error(f"Failed to send error message: {e}")

async def any_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler untuk semua message yang bukan command (untuk debugging)"""
    if update.message and not update.message.text.startswith('/'):
        print(f"[TELEGRAM BOT] Received non-command message: {update.message.text}")
        logger.debug(f"Non-command message: {update.message.text}")

def start_bot():
    """Inisialisasi dan start Telegram bot"""
    print("\n" + "="*60)
    print("[TELEGRAM BOT] Checking configuration...")
    print("="*60)
    
    # Debug: print environment variables
    import os
    token_from_env = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id_from_env = os.getenv("TELEGRAM_CHAT_ID")
    
    print(f"[DEBUG] TELEGRAM_BOT_TOKEN from env: {'SET' if token_from_env else 'NOT SET'}")
    print(f"[DEBUG] TELEGRAM_CHAT_ID from env: {'SET' if chat_id_from_env else 'NOT SET'}")
    
    if not TELEGRAM_BOT_TOKEN or not AUTHORIZED_CHAT_ID:
        print("[TELEGRAM BOT] ❌ CONFIGURATION ERROR:")
        print(f"  TELEGRAM_BOT_TOKEN: {'✅ SET' if TELEGRAM_BOT_TOKEN else '❌ NOT SET'}")
        print(f"  TELEGRAM_CHAT_ID: {'✅ SET' if AUTHORIZED_CHAT_ID else '❌ NOT SET'}")
        print("[TELEGRAM BOT] Bot tidak dapat diinisialisasi tanpa token dan chat_id!")
        print("[TELEGRAM BOT] Pastikan .env file berisi:")
        print("[TELEGRAM BOT]   TELEGRAM_BOT_TOKEN=your_token")
        print("[TELEGRAM BOT]   TELEGRAM_CHAT_ID=your_chat_id")
        logger.warning("TELEGRAM_BOT_TOKEN atau TELEGRAM_CHAT_ID tidak ditemukan")
        logger.warning(f"TELEGRAM_BOT_TOKEN: {'SET' if TELEGRAM_BOT_TOKEN else 'NOT SET'}")
        logger.warning(f"TELEGRAM_CHAT_ID: {'SET' if AUTHORIZED_CHAT_ID else 'NOT SET'}")
        print("="*60 + "\n")
        return None
    
    print("[TELEGRAM BOT] ✅ Configuration OK:")
    print(f"  TELEGRAM_BOT_TOKEN: ✅ SET (length: {len(TELEGRAM_BOT_TOKEN)} chars)")
    print(f"  TELEGRAM_CHAT_ID: ✅ SET ({AUTHORIZED_CHAT_ID})")
    
    try:
        print("[TELEGRAM BOT] Initializing bot...")
        logger.info("Initializing Telegram bot...")
        app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
        
        # Add error handler
        app.add_error_handler(error_handler)
        
        # Add command handlers (prioritas tinggi)
        app.add_handler(CommandHandler("start", start_command))
        app.add_handler(CommandHandler("test_scan", test_scan))
        app.add_handler(CommandHandler("test", test_command))
        
        # Add message handler untuk debugging (prioritas rendah)
        from telegram.ext import MessageHandler, filters
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, any_message_handler), group=1)
        
        print("[TELEGRAM BOT] ✅ Bot initialized successfully!")
        print(f"[TELEGRAM BOT] Commands registered: /start, /test_scan, /test")
        print(f"[TELEGRAM BOT] Authorized chat_id: {AUTHORIZED_CHAT_ID}")
        print(f"[TELEGRAM BOT] Bot token: {TELEGRAM_BOT_TOKEN[:20]}...{TELEGRAM_BOT_TOKEN[-10:]}")
        print("="*60 + "\n")
        logger.info(f"Telegram bot initialized successfully for chat_id: {AUTHORIZED_CHAT_ID}")
        return app
    except Exception as e:
        print(f"[TELEGRAM BOT] ❌ INITIALIZATION ERROR: {e}")
        print(f"[TELEGRAM BOT] Error type: {type(e).__name__}")
        import traceback
        print(f"[TELEGRAM BOT] Traceback:\n{traceback.format_exc()}")
        print("="*60 + "\n")
        logger.error(f"Failed to initialize Telegram bot: {e}", exc_info=True)
        return None