import asyncio
from aiogram import Bot
from config import BOT_TOKEN


async def find_my_id():
    bot = Bot(token=BOT_TOKEN)

    print("🤖 Бот запущен для поиска вашего ID...")
    print("📱 Откройте Telegram и напишите ЛЮБОЕ сообщение вашему боту")
    print("⏳ Ожидаю сообщение...")

    try:
        # Получаем последние обновления
        updates = await bot.get_updates()

        if updates:
            last_message = updates[-1].message
            if last_message:
                user_id = last_message.from_user.id
                first_name = last_message.from_user.first_name

                print(f"\n🎉 Найден пользователь!")
                print(f"👤 Имя: {first_name}")
                print(f"🆔 Ваш Telegram ID: {user_id}")
                print(f"\n📝 Скопируйте этот ID и вставьте в файл bot.py:")
                print(f"EXPERT_IDS = [{user_id}]")
            else:
                print("❌ Сообщения не найдены")
        else:
            print("❌ Не получено ни одного сообщения")
            print("💡 Отправьте сообщение вашему боту и запустите скрипт снова")

    except Exception as e:
        print(f"❌ Ошибка: {e}")
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(find_my_id())