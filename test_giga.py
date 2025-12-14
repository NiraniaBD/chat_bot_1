# test_giga.py
import asyncio
import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from gigachat_client import GigaChatClient


async def test_gigachat():
    # Ваш ключ авторизации
    AUTH_KEY = "MDE5YjFkNDgtNWI4Mi03NTkyLTk5MDMtOGU5N2VmYjU4YjA3OjMyMDVjNTUyLWI1NWEtNDQzNi1iODQxLWQyZjhjZGE1NWVkNA=="
    SCOPE = "GIGACHAT_API_PERS"

    print("=" * 50)
    print("Тестирование GigaChat API")
    print("=" * 50)

    client = GigaChatClient(auth_key=AUTH_KEY, scope=SCOPE)

    # Тестовые вопросы
    test_questions = [
        "Что делать при головной боли?",
        "Как укрепить иммунитет?",
        "Какие симптомы у гриппа?",
    ]

    for i, question in enumerate(test_questions, 1):
        print(f"\nТест {i}: {question}")
        print("-" * 30)

        try:
            response = await client.generate_response(question, model="GigaChat-2-Pro")
            print(f"Ответ:\n{response}")
        except Exception as e:
            print(f"Ошибка: {e}")


if __name__ == "__main__":
    asyncio.run(test_gigachat())