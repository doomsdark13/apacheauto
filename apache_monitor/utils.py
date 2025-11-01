import hashlib
import os
from datetime import datetime

def sha256sum(filepath):
    if not os.path.isfile(filepath):
        return None
    hash_sha256 = hashlib.sha256()
    try:
        with open(filepath, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_sha256.update(chunk)
    except (OSError, IOError):
        return None
    return hash_sha256.hexdigest()

def sanitize_for_telegram(text):
    # Escape characters that break Telegram MarkdownV2
    for c in "_*[]()~`>#+-=|{}.!":
        text = text.replace(c, "\\" + c)
    return text

def now_str():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")