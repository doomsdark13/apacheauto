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
    """
    Escape characters yang reserved di Telegram MarkdownV2.
    Menurut dokumentasi Telegram, karakter yang perlu di-escape:
    _ * [ ] ( ) ~ ` > # + - = | { } . !
    """
    if not isinstance(text, str):
        text = str(text)
    
    # Urutan penting: escape backslash dulu untuk menghindari double escape
    text = text.replace("\\", "\\\\")
    
    # Kemudian escape karakter reserved lainnya
    reserved_chars = ["_", "*", "[", "]", "(", ")", "~", "`", ">", "#", "+", "-", "=", "|", "{", "}", ".", "!"]
    for char in reserved_chars:
        text = text.replace(char, "\\" + char)
    
    return text

def now_str():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")