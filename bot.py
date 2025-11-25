import asyncio
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardRemove, InlineKeyboardMarkup, InlineKeyboardButton
import aiohttp
import json
from datetime import datetime

from config import BOT_TOKEN, MISTRAL_API_KEY
from database import session, UserRequest, DraftAnswer
from keyboards import get_expert_keyboard

# Настройка логирования
logging.basicConfig(level=logging.INFO)

# Инициализация бота и диспетчера
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Список ID экспертов (замените на реальные ID)
EXPERT_IDS = [982232323]  # Ваш Telegram ID

# Глобальный словарь для отслеживания редактирования
editing_sessions = {}

# Защита от множественных нажатий (anti-flood)
processing_requests = set()


class MistralAPI:
    def __init__(self, api_key):
        self.api_key = api_key
        self.base_url = "https://api.mistral.ai/v1"

    def clean_question(self, question):
        """Очищает вопрос от приветствий и обращений"""
        # Список приветствий и обращений для удаления
        greetings = [
            "здравствуйте", "добрый день", "добрый вечер", "доброе утро",
            "привет", "доброй ночи", "татьяна", "николаевна", "татьяна николаевна",
            "уважаемая", "уважаемый", "администратор", "админ"
        ]

        # Разбиваем вопрос на слова
        words = question.lower().split()

        # Удаляем приветствия из начала вопроса
        cleaned_words = []
        skip_greetings = True  # Флаг для пропуска приветствий в начале

        for word in words:
            # Проверяем, является ли слово приветствием
            is_greeting = any(greeting in word for greeting in greetings)

            if skip_greetings and is_greeting:
                continue  # Пропускаем приветствие
            else:
                cleaned_words.append(word)
                skip_greetings = False  # После первого не-приветствия перестаем пропускать

        cleaned_question = ' '.join(cleaned_words)

        # Если после очистки вопрос пустой, возвращаем оригинал
        if not cleaned_question.strip():
            return question

        # Делаем первую букву заглавной
        cleaned_question = cleaned_question[0].upper() + cleaned_question[1:]

        return cleaned_question

    def is_health_related(self, question):
        """Проверяет, относится ли вопрос к здоровью"""
        health_keywords = [
            # Симптомы и боли
            'болит', 'боль', 'симптом', 'кашель', 'насморк', 'температур', 'жар', 'озноб',
            'тошнит', 'рвота', 'понос', 'запор', 'головокружени', 'слабость', 'усталост',
            'зуд', 'сып', 'покраснен', 'отек', 'опухол', 'воспален',

            # Органы и системы
            'голов', 'горл', 'нос', 'ух', 'глаз', 'зуб', 'живот', 'кишечни', 'желудок',
            'сердц', 'сосуд', 'давлен', 'пульс', 'дыхание', 'легк', 'бронх',
            'печен', 'почк', 'мочевой', 'спин', 'поясниц', 'шея', 'сустав', 'кост', 'мышц',
            'кож', 'волос', 'ногт',

            # Состояния и заболевания
            'здоров', 'болезн', 'заболеван', 'медицин', 'врач', 'доктор', 'больничн',
            'простуда', 'грипп', 'орви', 'аллерг', 'инфекц', 'вирус', 'бактери',
            'диабет', 'давлен', 'холестерин', 'иммунит', 'стресс', 'депресс', 'тревог',
            'бессонниц', 'сон', 'усталост',

            # Лечение и профилактика
            'лечен', 'терапи', 'профилактик', 'диагноз', 'анализ', 'обследован',
            'таблетк', 'лекарств', 'препарат', 'прививк', 'вакцин',
            'операц', 'хирург',

            # Образ жизни
            'питание', 'диет', 'еда', 'пить', 'вод', 'спорт', 'физкультур', 'зарядк',
            'упражнен', 'бег', 'ходьб', 'плаван', 'вес', 'похуден', 'ожирен',
            'витамин', 'минерал', 'протеин', 'калори',
            'курени', 'алкогол', 'наркотик',

            # Общие медицинские вопросы
            'что делать', 'как лечить', 'чем лечить', 'признак', 'проявлен', 'ощущен',
            'помощ', 'совет', 'рекомендац', 'опасн', 'риск', 'последств'
        ]

        question_lower = question.lower()

        # Расширенная проверка - ищем частичное совпадение
        for keyword in health_keywords:
            if keyword in question_lower:
                return True

        # Дополнительная проверка по контексту
        health_context_words = ['кашель', 'насморк', 'температура', 'давление', 'пульс']
        for word in health_context_words:
            if word in question_lower:
                return True

        # Если вопрос содержит "что делать при" + любой симптом - считаем медицинским
        if 'что делать при' in question_lower or 'что делать если' in question_lower:
            return True

        # Если вопрос содержит "как лечить" - считаем медицинским
        if 'как лечить' in question_lower or 'чем лечить' in question_lower:
            return True

        return False


    async def generate_response(self, question):
        """Генерирует ответ с помощью Mistral AI"""

        # Очищаем вопрос от приветствий
        cleaned_question = self.clean_question(question)
        logging.info(f"Оригинальный вопрос: '{question}'")
        logging.info(f"Очищенный вопрос: '{cleaned_question}'")

        # Проверка на медицинскую тематику
        if not self.is_health_related(question):
            return "Я специализируюсь только на вопросах здоровья. Пожалуйста, задайте вопрос о здоровом образе жизни, симптомах или общих медицинских темах."

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        # Промпт с ограничениями для медицинского контекста
        system_prompt = """Ты - медицинский информационный ассистент. Давай краткие, информативные ответы на вопросы о здоровье.

        📋 ОСНОВНЫЕ ПРАВИЛА:
        • Ответ: 3-5 предложений максимум
        • Начинай сразу с сути, без приветствий
        • Не используй имена и обращения
        • Не ставь диагнозы и не назначай лечение

        🚫 ЗАПРЕЩЕНО:
        • "Здравствуйте", "Добрый день" и другие приветствия
        • Обращения по имени ("Татьяна Николаевна" и т.д.)
        • Конкретные медицинские назначения
        • Призывы к самолечению

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
        Ответ: "При головной боли может помочь отдых в тихом помещении и достаточное потребление воды. Головная боль может быть вызвана различными причинами. Для точной диагностики рекомендую обратиться к терапевту."

        Вопрос: "Как укрепить иммунитет?"
        Ответ: "Для поддержания иммунитета важны сбалансированное питание, достаточный сон и физическая активность. Иммунная система требует комплексного подхода. Проконсультируйтесь с врачом для индивидуальных рекомендаций."

        Вопрос не о здоровье: "Сколько стоит iPhone?"
        Ответ: "Я специализируюсь только на вопросах здоровья. Задайте вопрос о здоровом образе жизни или общих медицинских темах."

        Следуй этим правилам строго."""

        data = {
            "model": "mistral-tiny",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": question}
            ],
            "max_tokens": 500,
            "temperature": 0.7
        }

        async with aiohttp.ClientSession() as http_session:
            async with http_session.post(
                    f"{self.base_url}/chat/completions",
                    headers=headers,
                    json=data
            ) as response:
                result = await response.json()
                return result['choices'][0]['message']['content']


def clean_response(self, response):
    """Очищает ответ от приветствий и обращений"""
    # Удаляем приветствия из начала ответа
    greetings = [
        "здравствуйте", "добрый день", "добрый вечер", "доброе утро",
        "привет", "доброй ночи", "уважаем", "татьяна", "николаевна",
        "пользователь", "клиент", "дорогой", "дорогая"
    ]

    lines = response.split('\n')
    cleaned_lines = []

    for line in lines:
        line_lower = line.lower().strip()
        # Пропускаем строки, которые содержат только приветствия
        if any(greeting in line_lower for greeting in greetings) and len(line_lower.split()) <= 3:
            continue
        # Удаляем приветствия из начала строк
        for greeting in greetings:
            if line_lower.startswith(greeting):
                line = line[len(greeting):].lstrip(' ,!:-')
                line_lower = line.lower().strip()
        cleaned_lines.append(line)

    cleaned_response = '\n'.join(cleaned_lines).strip()

    # Если после очистки ответ пустой, возвращаем оригинал
    if not cleaned_response:
        return response

    # Убеждаемся, что ответ начинается с заглавной буквы
    if cleaned_response and cleaned_response[0].islower():
        cleaned_response = cleaned_response[0].upper() + cleaned_response[1:]

    return cleaned_response

mistral_api = MistralAPI(MISTRAL_API_KEY)


@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    """Обработчик команды /start"""
    welcome_text = """
👋 Добро пожаловать в чат-бот помощник по здоровью!

Задайте ваш вопрос о здоровье, и наш ИИ-помощник вместе с медицинским экспертом подготовит для вас ответ.

⚠️ Важно: 
• Это информационная поддержка, а не замена врачу
• Не используйте ответы для самолечения
• При серьезных симптомах обращайтесь к врачу
"""
    await message.answer(welcome_text, reply_markup=ReplyKeyboardRemove())


@dp.message(F.text & ~F.from_user.id.in_(EXPERT_IDS))
async def handle_user_question(message: types.Message):
    """Обработка вопросов ТОЛЬКО от обычных пользователей (не экспертов)"""
    user_id = message.from_user.id
    question = message.text

    # Сохраняем вопрос в БД
    request = UserRequest(
        user_id=user_id,
        question=question,
        status='waiting'
    )
    session.add(request)
    session.commit()

    # Уведомляем пользователя
    await message.answer("✅ Ваш вопрос принят на модерацию. Ответ поступит в течение 12 часов.")

    # Генерируем черновик ответа с помощью Mistral
    try:
        llm_response = await mistral_api.generate_response(question)

        # Сохраняем черновик в БД
        draft = DraftAnswer(
            request_id=request.id,
            llm_response=llm_response
        )
        session.add(draft)
        session.commit()

        # Уведомляем экспертов о новом вопросе
        await notify_experts(request.id, question, llm_response)

    except Exception as e:
        logging.error(f"Ошибка при генерации ответа: {e}")
        await message.answer("⚠️ Произошла ошибка при обработке вопроса. Попробуйте позже.")


@dp.message(F.text & F.from_user.id.in_(EXPERT_IDS))
async def handle_expert_text(message: types.Message):
    """Обработка ВСЕХ текстовых сообщений от экспертов"""

    # Проверяем, находится ли эксперт в режиме редактирования
    if message.from_user.id in editing_sessions:
        request_id = editing_sessions[message.from_user.id]

        # Находим черновик в БД
        draft = session.query(DraftAnswer).filter_by(request_id=request_id).first()

        if draft:
            # Сохраняем отредактированный текст
            draft.expert_edited_response = message.text
            session.commit()

            # Удаляем сессию редактирования
            del editing_sessions[message.from_user.id]

            # Показываем клавиатуру с действиями
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(text="✅ Опубликовать", callback_data=f"approve_{request_id}"),
                    InlineKeyboardButton(text="✏️ Еще раз редактировать", callback_data=f"edit_{request_id}")
                ],
                [
                    InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject_{request_id}")
                ]
            ])

            await message.answer(
                f"✅ Ответ отредактирован!\n\n"
                f"📋 Новый текст:\n{message.text}\n\n"
                f"🔄 Выберите действие:",
                reply_markup=keyboard
            )

            logging.info(f"Эксперт {message.from_user.id} отредактировал ответ на запрос {request_id}")
        else:
            await message.answer("❌ Ошибка: черновик не найден")
            if message.from_user.id in editing_sessions:
                del editing_sessions[message.from_user.id]
    else:
        # Эксперт пишет обычное сообщение (не в режиме редактирования)
        await message.answer("🤖 Вы эксперт. Используйте кнопки модерации для работы с вопросами.")


async def notify_experts(request_id: int, question: str, llm_response: str):
    """Уведомляет экспертов о новом вопросе"""
    notification_text = f"""
🆕 Новый вопрос для модерации (ID: {request_id})

❓ Вопрос пользователя:
{question}

🤖 Черновик ответа от ИИ:
{llm_response}
"""

    for expert_id in EXPERT_IDS:
        try:
            await bot.send_message(
                expert_id,
                notification_text,
                reply_markup=get_expert_keyboard(request_id)
            )
        except Exception as e:
            logging.error(f"Не удалось уведомить эксперта {expert_id}: {e}")


# Обработчик нажатия на кнопку "Опубликовать"
@dp.callback_query(F.data.startswith("approve_"))
async def approve_response(callback: types.CallbackQuery):
    """Одобрение ответа экспертом"""

    # Защита от множественных нажатий
    if callback.data in processing_requests:
        await callback.answer("⏳ Запрос уже обрабатывается...", show_alert=True)
        return
    processing_requests.add(callback.data)

    try:
        request_id = int(callback.data.split("_")[1])

        # Находим запрос и черновик в БД
        request = session.query(UserRequest).filter_by(id=request_id).first()
        draft = session.query(DraftAnswer).filter_by(request_id=request_id).first()

        if request and draft:
            # Обновляем статус
            request.status = 'approved'

            # Используем отредактированный ответ или оригинальный от ИИ
            final_response = draft.expert_edited_response or draft.llm_response

            # Добавляем дисклеймер ТОЛЬКО для медицинских ответов
            if "Я специализируюсь только на вопросах здоровья" not in final_response:
                final_response = f"{final_response}\n\n⚠️ Этот ответ подготовлен ИИ и проверен медицинским специалистом. Он не заменяет очную консультацию врача."

            # Отправляем ответ пользователю
            try:
                await bot.send_message(
                    chat_id=request.user_id,
                    text=final_response
                )
                # Обновляем время решения
                draft.decision_time = datetime.now()
                draft.expert_id = callback.from_user.id

                session.commit()

                # Уведомляем эксперта об успехе
                await callback.message.edit_text(
                    f"✅ Ответ опубликован и отправлен пользователю!\n\n"
                    f"ID запроса: {request_id}",
                    reply_markup=None
                )

            except Exception as e:
                await callback.answer(f"❌ Ошибка отправки: {e}", show_alert=True)
        else:
            await callback.answer("❌ Запрос не найден", show_alert=True)

    finally:
        # Убираем из множества обработки после завершения
        if callback.data in processing_requests:
            processing_requests.remove(callback.data)


# Обработчик нажатия на кнопку "Отклонить"
@dp.callback_query(F.data.startswith("reject_"))
async def reject_response(callback: types.CallbackQuery):
    """Отклонение ответа экспертом"""

    # Защита от множественных нажатий
    if callback.data in processing_requests:
        await callback.answer("⏳ Запрос уже обрабатывается...", show_alert=True)
        return
    processing_requests.add(callback.data)

    try:
        request_id = int(callback.data.split("_")[1])

        # Находим запрос в БД
        request = session.query(UserRequest).filter_by(id=request_id).first()
        draft = session.query(DraftAnswer).filter_by(request_id=request_id).first()

        if request:
            # Обновляем статус
            request.status = 'rejected'

            # Отправляем шаблонный ответ пользователю
            try:
                await bot.send_message(
                    chat_id=request.user_id,
                    text="❌ К сожалению, мы не можем ответить на этот вопрос. Обратитесь к врачу за индивидуальной консультацией."
                )

                # Обновляем время решения
                if draft:
                    draft.decision_time = datetime.now()
                    draft.expert_id = callback.from_user.id

                session.commit()

                # Уведомляем эксперта об успехе
                await callback.message.edit_text(
                    f"❌ Ответ отклонен. Пользователь уведомлен.\n\n"
                    f"ID запроса: {request_id}",
                    reply_markup=None
                )

            except Exception as e:
                await callback.answer(f"❌ Ошибка отправки: {e}", show_alert=True)
        else:
            await callback.answer("❌ Запрос не найден", show_alert=True)

    finally:
        # Убираем из множества обработки после завершения
        if callback.data in processing_requests:
            processing_requests.remove(callback.data)


# Обработчик нажатия на кнопку "Редактировать"
@dp.callback_query(F.data.startswith("edit_"))
async def start_editing_response(callback: types.CallbackQuery):
    """Начало редактирования ответа"""

    # Защита от множественных нажатий
    if callback.data in processing_requests:
        await callback.answer("⏳ Запрос уже обрабатывается...", show_alert=True)
        return
    processing_requests.add(callback.data)

    try:
        # Проверяем, что это эксперт
        if callback.from_user.id not in EXPERT_IDS:
            await callback.answer("❌ У вас нет прав для редактирования.", show_alert=True)
            return

        request_id = int(callback.data.split("_")[1])

        # Находим черновик в БД
        draft = session.query(DraftAnswer).filter_by(request_id=request_id).first()

        if draft:
            # Сохраняем сессию редактирования
            editing_sessions[callback.from_user.id] = request_id

            # Определяем, какой текст показывать для редактирования
            # Показываем отредактированный текст, если он есть, иначе оригинальный от ИИ
            current_text = draft.expert_edited_response or draft.llm_response

            # Создаем клавиатуру с кнопкой отмены
            cancel_keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="❌ Отменить редактирование", callback_data=f"cancel_edit_{request_id}")]
            ])

            # Просим эксперта ввести новый текст
            await callback.message.answer(
                f"✏️ Редактирование ответа (ID запроса: {request_id})\n\n"
                f"Текущий текст ответа:\n"
                f"────────────────────\n"
                f"{current_text}\n"
                f"────────────────────\n\n"
                f"📝 Пришлите исправленный текст ответа СЕЙЧАС:\n\n"
                f"💡 После отправки текста вы сможете выбрать действие.",
                reply_markup=cancel_keyboard
            )

            await callback.answer("✏️ Режим редактирования. Пришлите новый текст ответа.")
        else:
            await callback.answer("❌ Черновик не найден", show_alert=True)

    finally:
        # Убираем из множества обработки после завершения
        if callback.data in processing_requests:
            processing_requests.remove(callback.data)


# Обработчик отмены редактирования
@dp.callback_query(F.data.startswith("cancel_edit_"))
async def cancel_editing(callback: types.CallbackQuery):
    """Отмена редактирования"""

    # Защита от множественных нажатий
    if callback.data in processing_requests:
        await callback.answer("⏳ Запрос уже обрабатывается...", show_alert=True)
        return
    processing_requests.add(callback.data)

    try:
        request_id = int(callback.data.split("_")[2])

        # Удаляем сессию редактирования если существует
        if callback.from_user.id in editing_sessions:
            del editing_sessions[callback.from_user.id]

        # Находим запрос и черновик в БД
        request = session.query(UserRequest).filter_by(id=request_id).first()
        draft = session.query(DraftAnswer).filter_by(request_id=request_id).first()

        if request and draft:
            # Определяем текущий текст ответа (отредактированный или оригинальный)
            current_response = draft.expert_edited_response or draft.llm_response

            # Редактируем исходное сообщение вместо создания нового
            await callback.message.edit_text(
                f"🆕 Вопрос для модерации (ID: {request_id})\n\n"
                f"❓ Вопрос пользователя:\n{request.question}\n\n"
                f"🤖 Текст ответа:\n{current_response}",
                reply_markup=get_expert_keyboard(request_id)
            )

            # Удаляем сообщение с приглашением к редактированию (если оно есть)
            try:
                await callback.message.delete()
            except:
                pass  # Игнорируем ошибки если сообщение уже удалено

        else:
            await callback.answer("❌ Запрос не найден", show_alert=True)

        await callback.answer("Редактирование отменено")

    finally:
        # Убираем из множества обработки после завершения
        if callback.data in processing_requests:
            processing_requests.remove(callback.data)


# Обработчик нажатия на кнопку "Сгенерировать заново"
@dp.callback_query(F.data.startswith("regenerate_"))
async def regenerate_response(callback: types.CallbackQuery):
    """Повторная генерация ответа для того же вопроса"""

    # Защита от множественных нажатий
    if callback.data in processing_requests:
        await callback.answer("⏳ Запрос уже обрабатывается...", show_alert=True)
        return
    processing_requests.add(callback.data)

    try:
        # Проверяем, что это эксперт
        if callback.from_user.id not in EXPERT_IDS:
            await callback.answer("❌ У вас нет прав для генерации ответов.", show_alert=True)
            return

        request_id = int(callback.data.split("_")[1])

        # Находим запрос в БД
        request = session.query(UserRequest).filter_by(id=request_id).first()

        if request:
            try:
                # Уведомляем эксперта о начале генерации
                await callback.answer("🔄 Генерирую новый ответ...")

                # Генерируем новый ответ
                new_llm_response = await mistral_api.generate_response(request.question)

                # Находим или создаем черновик
                draft = session.query(DraftAnswer).filter_by(request_id=request_id).first()
                if draft:
                    # Обновляем существующий черновик
                    draft.llm_response = new_llm_response
                    draft.expert_edited_response = None  # Сбрасываем редактирование
                    draft.expert_id = callback.from_user.id
                else:
                    # Создаем новый черновик
                    draft = DraftAnswer(
                        request_id=request_id,
                        llm_response=new_llm_response,
                        expert_id=callback.from_user.id
                    )
                    session.add(draft)

                session.commit()

                # Обновляем сообщение эксперта с новым ответом
                await callback.message.edit_text(
                    f"🆕 Новый сгенерированный ответ (ID: {request_id})\n\n"
                    f"❓ Вопрос пользователя:\n{request.question}\n\n"
                    f"🤖 Черновик ответа от ИИ:\n{new_llm_response}",
                    reply_markup=get_expert_keyboard(request_id)
                )

                logging.info(f"Эксперт {callback.from_user.id} перегенерировал ответ на запрос {request_id}")

            except Exception as e:
                logging.error(f"Ошибка при перегенерации ответа: {e}")
                await callback.answer(f"❌ Ошибка генерации: {e}", show_alert=True)
        else:
            await callback.answer("❌ Запрос не найден", show_alert=True)

    finally:
        # Убираем из множества обработки после завершения
        if callback.data in processing_requests:
            processing_requests.remove(callback.data)


async def main():
    """Запуск бота"""
    logging.info("Бот запущен")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())