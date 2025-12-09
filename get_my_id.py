import asyncio
import sys
from aiogram import Bot
from aiogram import Dispatcher
from aiogram.types import Message
from config import BOT_TOKEN

# Глобальная переменная для хранения найденного ID
found_user = None
event = asyncio.Event()


async def on_message(message: Message):
    """Обработчик входящих сообщений"""
    global found_user

    user = message.from_user
    found_user = {
        'id': user.id,
        'first_name': user.first_name,
        'last_name': user.last_name,
        'username': user.username
    }

    # Сигнализируем, что пользователь найден
    event.set()


async def wait_for_user():
    """Ждет сообщение от пользователя"""
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()

    # Регистрируем обработчик
    dp.message.register(on_message)

    print("🤖 Бот запущен для поиска вашего ID...")
    print("📱 Откройте Telegram и напишите ЛЮБОЕ сообщение вашему боту")
    print("⏳ Ожидаю сообщение (неограниченное время)...")
    print("💡 Для выхода нажмите Ctrl+C")
    print("-" * 50)

    try:
        # Очищаем старые обновления
        await bot.delete_webhook(drop_pending_updates=True)

        # Запускаем поллинг
        polling_task = asyncio.create_task(dp.start_polling(bot))

        # Ждем, пока пользователь отправит сообщение
        await event.wait()

        # Отменяем поллинг
        polling_task.cancel()
        try:
            await polling_task
        except asyncio.CancelledError:
            pass

        return found_user

    finally:
        await bot.session.close()


def main():
    """Основная функция"""
    print("=" * 50)
    print("🆔 ПОИСК ТЕЛЕГРАМ ID ПОЛЬЗОВАТЕЛЯ")
    print("=" * 50)

    if not BOT_TOKEN:
        print("❌ BOT_TOKEN не найден!")
        print("Убедитесь, что файл .env существует и содержит:")
        print("BOT_TOKEN=ваш_токен_бота")
        sys.exit(1)

    try:
        user_info = asyncio.run(wait_for_user())

        if user_info:
            print("\n" + "=" * 50)
            print("🎉 ПОЛЬЗОВАТЕЛЬ НАЙДЕН!")
            print("=" * 50)
            print(f"👤 Имя: {user_info['first_name']}")
            if user_info['last_name']:
                print(f"👤 Фамилия: {user_info['last_name']}")
            if user_info['username']:
                print(f"📝 Username: @{user_info['username']}")
            print(f"🆔 Telegram ID: {user_info['id']}")
            print("=" * 50)

            print(f"\n📝 Скопируйте ID в нужное место:")
            print(f"1. В bot.py: EXPERT_IDS = [{user_info['id']}]")
            print(f"2. Или в config.py: EXPERT_IDS = [{user_info['id']}]")
            print(f"\n💡 Для нескольких экспертов: EXPERT_IDS = [{user_info['id']}, другой_id]")

    except KeyboardInterrupt:
        print("\n\n👋 Программа прервана пользователем")
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")


if __name__ == "__main__":
    main()