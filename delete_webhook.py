import os
import asyncio
from telegram import Bot
from dotenv import load_dotenv

load_dotenv()


async def delete_webhook():
    bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
    if not bot_token:
        print("❌ TELEGRAM_BOT_TOKEN не найден в .env файле")
        return

    bot = Bot(token=bot_token)

    try:
        # Удаляем вебхук
        result = await bot.delete_webhook()
        if result:
            print("✅ Вебхук успешно удален!")
        else:
            print("❌ Не удалось удалить вебхук")

        # Проверяем статус
        webhook_info = await bot.get_webhook_info()
        print(f"📊 Статус вебхука: {'активен' if webhook_info.url else 'не активен'}")
        if webhook_info.url:
            print(f"🔗 URL вебхука: {webhook_info.url}")

    except Exception as e:
        print(f"❌ Ошибка при удалении вебхука: {e}")


if __name__ == "__main__":
    asyncio.run(delete_webhook())