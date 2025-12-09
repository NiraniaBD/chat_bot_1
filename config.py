import os
from dotenv import load_dotenv

load_dotenv()

# Telegram Bot
BOT_TOKEN = os.getenv("BOT_TOKEN")

# GigaChat API
GIGACHAT_AUTH_KEY = os.getenv("GIGACHAT_AUTH_KEY", "MDE5YWZlY2EtNDBiZS03NWQxLWJiZDgtMzcwMWQ4MTc3MGNlOjViNzI4NzJjLWE3NjgtNDJhMy1iZmMyLWJkODc4MTU1NTc3Ng==")
GIGACHAT_SCOPE = os.getenv("GIGACHAT_SCOPE", "GIGACHAT_API_PERS")