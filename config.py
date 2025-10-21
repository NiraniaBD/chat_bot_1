import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
MISTRAL_API_KEY = os.getenv('MISTRAL_API_KEY')

if not BOT_TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN не найден в .env файле")

if not MISTRAL_API_KEY:
    raise ValueError("MISTRAL_API_KEY не найден в .env файле")