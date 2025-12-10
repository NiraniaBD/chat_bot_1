import os
from dotenv import load_dotenv

load_dotenv()

# Telegram Bot
BOT_TOKEN = os.getenv("BOT_TOKEN")

# GigaChat API
GIGACHAT_AUTH_KEY = os.getenv("GIGACHAT_AUTH_KEY", "MDE5YjAzYmEtNjRlZS03MzAyLWIxNmMtMDg3YzI4YmM1M2I4OmEyOWI3NDA2LTZjZWYtNGQ4YS04MzIyLTg0MzhkNjY2NmQ4MQ==")
GIGACHAT_SCOPE = os.getenv("GIGACHAT_SCOPE", "GIGACHAT_API_PERS")