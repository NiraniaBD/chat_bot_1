import asyncio
import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from gigachat_client import GigaChatClient
from config import GIGACHAT_AUTH_KEY, GIGACHAT_SCOPE


async def test_bot_integration():
    print("=" * 50)
    print("Тестирование интеграции GigaChat с ботом")
    print("=" * 50)

    client = GigaChatClient(
        auth_key=GIGACHAT_AUTH_KEY,
        scope=GIGACHAT_SCOPE
    )

    # Тестовые вопросы
    test_questions = [
        "Добрый день, Татьяна Николаевна! У меня болит голова, что делать?",
        "Здравствуйте! Как избавиться от кашля?",
        "Что посоветуете при температуре 38?",
    ]

    for i, question in enumerate(test_questions, 1):
        print(f"\nТест {i}: {question}")
        print("-" * 30)

        try:
            # Генерация ответа
            response = await client.generate_response(question)
            print(f"Сгенерированный ответ:\n{response}")

            # Проверка добавления дисклеймера
            final_response = client.add_greeting_disclaimer(response)
            print(f"\nОтвет с дисклеймером:\n{final_response}")

        except Exception as e:
            print(f"Ошибка: {e}")


if __name__ == "__main__":
    asyncio.run(test_bot_integration())