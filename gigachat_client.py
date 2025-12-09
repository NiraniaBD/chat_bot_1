# gigachat_client.py
import asyncio
import aiohttp
import json
import logging
import uuid
import ssl
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class GigaChatClient:
    def __init__(self, auth_key: str, scope: str = "GIGACHAT_API_PERS"):
        """
        Инициализация клиента GigaChat

        :param auth_key: Ключ авторизации (Authorization key из личного кабинета)
        :param scope: Scope (обычно GIGACHAT_API_PERS)
        """
        self.auth_key = auth_key
        self.scope = scope
        self.auth_url = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"
        self.chat_url = "https://gigachat.devices.sberbank.ru/api/v1/chat/completions"
        self.access_token = None
        self.token_expiry = None
        self.rquid = str(uuid.uuid4())  # Генерируем уникальный RqUID

        # Создаем контекст SSL без проверки сертификатов
        self.ssl_context = ssl.create_default_context()
        self.ssl_context.check_hostname = False
        self.ssl_context.verify_mode = ssl.CERT_NONE

    async def _get_access_token(self) -> str:
        """Получает access token для авторизации запросов"""
        # Если токен ещё действителен (30 минут), используем его
        if self.access_token and self.token_expiry and datetime.now() < self.token_expiry:
            return self.access_token

        logger.info("Получаем новый access token для GigaChat...")

        headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
            'Accept': 'application/json',
            'RqUID': self.rquid,
            'Authorization': f'Basic {self.auth_key}'
        }

        payload = f'scope={self.scope}'

        try:
            # Создаем сессию с отключенной проверкой SSL
            async with aiohttp.ClientSession(
                    connector=aiohttp.TCPConnector(ssl=self.ssl_context)
            ) as session:

                async with session.post(
                        self.auth_url,
                        headers=headers,
                        data=payload
                ) as response:

                    if response.status == 200:
                        result = await response.json()
                        self.access_token = result.get("access_token")

                        if not self.access_token:
                            raise Exception("Access token не получен в ответе")

                        # Токен действует 30 минут
                        self.token_expiry = datetime.now() + timedelta(seconds=1800)
                        logger.info("Access token успешно получен")
                        return self.access_token
                    else:
                        error_text = await response.text()
                        logger.error(f"Ошибка при получении токена: {response.status} - {error_text}")
                        raise Exception(f"Ошибка авторизации: {response.status}")

        except Exception as e:
            logger.error(f"Ошибка в _get_access_token: {e}")
            raise

    async def generate_response(self, question: str, model: str = "GigaChat-2-Pro") -> str:
        """
        Генерирует ответ на вопрос пользователя

        :param question: Вопрос пользователя
        :param model: Модель GigaChat (GigaChat-2, GigaChat-2-Pro, GigaChat-2-Max)
        :return: Сгенерированный ответ
        """
        try:
            # Получаем токен
            token = await self._get_access_token()

            # Формируем медицинский промпт (можно использовать тот же, что и для Mistral)
            system_prompt = """Ты - медицинский информационный ассистент. Давай краткие, информативные ответы на вопросы о здоровье.

📋 ОСНОВНЫЕ ПРАВИЛА:
• Ответ: 3-5 предложений максимум
• Начинай сразу с сути, без приветствий
• Не используй имена и обращения
• Не ставь диагнозы и не назначай лечение
• Не добавляй приветствия в начале ответа

🚫 ЗАПРЕЩЕНО:
• "Здравствуйте", "Добрый день" и другие приветствия
• Обращения по имени ("Татьяна Николаевна" и т.д.)
• Конкретные медицинские назначения
• Призывы к самолечению
• Фразы "При головной боли может помочь..."

✅ РАЗРЕШЕНО:
• Общая информация о здоровом образе жизни
• Описание симптомов распространенных состояний
• Рекомендация обратиться к врачу

📝 ФОРМАТ ОТВЕТА:
1. Прямой ответ на вопрос (1-2 предложения)
2. Общая информация/контекст (1-2 предложения)
3. Рекомендация проконсультироваться с врачом

🎯 ПРИМЕРЫ:

Вопрос: "Что делать при головной боли?"
Ответ: "Отдохните в спокойной обстановке и пейте достаточно воды. Головная боль может быть вызвана различными причинами. Для точной диагностики обратитесь к терапевту."

Вопрос: "Как укрепить иммунитет?"
Ответ: "Поддерживайте сбалансированное питание, регулярную физическую активность и достаточный сон. Иммунная система требует комплексного подхода. Проконсультируйтесь с врачом для индивидуальных рекомендаций."

Следуй этим правилам строго."""

            # Подготавливаем запрос к чату
            payload = json.dumps({
                "model": model,
                "messages": [
                    {
                        "role": "system",
                        "content": system_prompt
                    },
                    {
                        "role": "user",
                        "content": question
                    }
                ],
                "temperature": 0.3,
                "max_tokens": 500,
                "repetition_penalty": 1.2,
                "profanity_check": True  # Проверка на ненормативную лексику
            })

            headers = {
                'Content-Type': 'application/json',
                'Accept': 'application/json',
                'Authorization': f'Bearer {token}'
            }

            # Создаем сессию с SSL контекстом
            async with aiohttp.ClientSession(
                    connector=aiohttp.TCPConnector(ssl=self.ssl_context)
            ) as session:

                async with session.post(
                        self.chat_url,
                        headers=headers,
                        data=payload
                ) as response:

                    if response.status == 200:
                        result = await response.json()
                        return result["choices"][0]["message"]["content"]
                    else:
                        error_text = await response.text()
                        logger.error(f"Ошибка GigaChat API: {response.status} - {error_text}")
                        return "Извините, произошла ошибка при генерации ответа. Пожалуйста, попробуйте позже."

        except Exception as e:
            logger.error(f"Ошибка в generate_response: {e}")
            return "Извините, произошла ошибка при обработке вопроса. Пожалуйста, попробуйте позже."

    def clean_response(self, response):
        """Очищает ответ от приветствий и обращений (опционально)"""
        # Если хотите оставить очистку, можно добавить
        return response

    def add_greeting_disclaimer(self, response: str) -> str:
        """
        Добавляет приветствие и дисклеймер к ответу

        Формат:
        1. Приветствие
        2. Основной ответ
        3. Дисклеймер (если это медицинский ответ)
        """
        # Проверяем, является ли ответ общим (не медицинским)
        is_general_response = "Я специализируюсь только на вопросах здоровья" in response

        # Добавляем приветствие в начало
        response_with_greeting = f"Здравствуйте!\n\n{response}"

        # Для медицинских ответов добавляем дисклеймер в конец
        if not is_general_response:
            response_with_greeting = f"{response_with_greeting}\n\n⚠️ Этот ответ подготовлен ИИ и проверен медицинским специалистом. Он не заменяет очную консультацию врача."

        return response_with_greeting