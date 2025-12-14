import os
from dotenv import load_dotenv

load_dotenv()

# Telegram Bot
BOT_TOKEN = os.getenv("BOT_TOKEN")

# GigaChat API
GIGACHAT_AUTH_KEY = os.getenv("GIGACHAT_AUTH_KEY", "MDE5YjFkNDgtNWI4Mi03NTkyLTk5MDMtOGU5N2VmYjU4YjA3OjMyMDVjNTUyLWI1NWEtNDQzNi1iODQxLWQyZjhjZGE1NWVkNA==")
GIGACHAT_SCOPE = os.getenv("GIGACHAT_SCOPE", "GIGACHAT_API_PERS")