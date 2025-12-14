import asyncio
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardRemove, InlineKeyboardMarkup, InlineKeyboardButton
import aiohttp
import json
from datetime import datetime

from config import BOT_TOKEN, GIGACHAT_AUTH_KEY, GIGACHAT_SCOPE
from database import session, UserRequest, DraftAnswer
from keyboards import get_expert_keyboard
from gigachat_client import GigaChatClient

from question_processor import QuestionProcessor
question_processor = QuestionProcessor()


giga_client = GigaChatClient(
    auth_key=GIGACHAT_AUTH_KEY,
    scope=GIGACHAT_SCOPE
)

# Настройка логирования
logging.basicConfig(level=logging.INFO)

# Инициализация бота и диспетчера
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Список ID экспертов
EXPERT_IDS = [753655653] #Даша 982232323, Оля 1552323966, Татьяна Бобышева 753655653

# Глобальный словарь для отслеживания редактирования
editing_sessions = {}

# Новый словарь для хранения message_id сообщений с кнопками
expert_messages = {}  # ключ: (expert_id, request_id), значение: message_id

# Защита от множественных нажатий
processing_requests = set()

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    """Обработчик команды /start - разные сообщения для пользователей и экспертов"""

    user_id = message.from_user.id

    # Проверяем, является ли пользователь экспертом
    if user_id in EXPERT_IDS:
        # Приветствие для эксперта
        welcome_text = """
👨‍⚕️ Добро пожаловать, эксперт!

Вы находитесь в панели модерации медицинского чат-бота.

📋 Ваши возможности:
1. Автоматически получаете уведомления о новых вопросах
2. Проверяете и редактируете ответы ИИ
3. Утверждаете или отклоняете ответы

⚡ Как работает система:
• Когда пользователь задает медицинский вопрос, вы получите уведомление
• В уведомлении будет вопрос и предварительный ответ от ИИ
• Вы можете: 
✅ Опубликовать
✏️ Редактировать
🔄 Сгенерировать заново
❌ Отклонить

⏳ Время на модерацию: до 12 часов
        """
        # Для экспертов можно сразу показать статистику или доступные вопросы
        # Например, добавить кнопку "Показать ожидающие вопросы"
        await message.answer(welcome_text, reply_markup=ReplyKeyboardRemove())

    else:
        # Приветствие для обычного пользователя
        welcome_text = """
👋 Добро пожаловать в чат-бот помощник по здоровью!

Задайте ваш вопрос о здоровье, и наш ИИ-помощник вместе с медицинским экспертом подготовит для вас ответ.

⚠️ Важно: 
• Это информационная поддержка, а не замена врачу
• Не используйте ответы для самолечения
• При серьезных симптомах обращайтесь к врачу
• Все ответы проверяются медицинским экспертом
• Время ответа: до 12 часов

📝 Просто напишите ваш вопрос о здоровье, и мы поможем!
        """
        await message.answer(welcome_text, reply_markup=ReplyKeyboardRemove())


@dp.message(F.text & ~F.from_user.id.in_(EXPERT_IDS))
async def handle_user_question(message: types.Message):
    """Обработка вопросов ТОЛЬКО от обычных пользователей (не экспертов)"""
    user_id = message.from_user.id
    original_question = message.text

    # 1. Обрабатываем вопрос
    processed = question_processor.process(original_question)

    logging.info(f"Обработка вопроса от пользователя {user_id}:")
    logging.info(f"  Оригинал: '{original_question}'")
    logging.info(f"  Очищенный: '{processed['cleaned']}'")
    logging.info(f"  Медицинский: {processed['is_medical']}")

    # 2. Если вопрос не медицинский - сразу отвечаем и НЕ сохраняем в БД
    if not processed["is_medical"]:
        await message.answer(
            "Я специализируюсь только на вопросах здоровья. Пожалуйста, задайте вопрос о здоровом образе жизни, симптомах или общих медицинских темах."
        )
        # НЕ создаем запись в БД для немедицинских вопросов
        return

    # 3. Сохраняем ОЧИЩЕННЫЙ вопрос в БД
    request = UserRequest(
        user_id=user_id,
        question=processed["cleaned"],
        original_question=original_question,  # Теперь это поле есть
        status='waiting'
    )
    session.add(request)
    session.commit()

    # 4. Уведомляем пользователя
    await message.answer("✅ Ваш вопрос принят на модерацию. Ответ поступит в течение 12 часов.")

    # 5. Генерируем черновик ответа на ОЧИЩЕННЫЙ вопрос с помощью GigaChat
    try:
        # Используем очищенный вопрос для генерации
        llm_response = await giga_client.generate_response(processed["cleaned"])

        # Очищаем ответ (опционально)
        cleaned_response = giga_client.clean_response(llm_response)

        # Сохраняем черновик в БД
        draft = DraftAnswer(
            request_id=request.id,
            llm_response=cleaned_response
        )
        session.add(draft)
        session.commit()

        # Уведомляем экспертов о новом вопросе
        # Отправляем экспертам ОРИГИНАЛЬНЫЙ вопрос для контекста
        await notify_experts(request.id, original_question, cleaned_response)

    except Exception as e:
        logging.error(f"Ошибка при генерации ответа: {e}")
        # Обновляем статус запроса на ошибку
        request.status = 'error'
        session.commit()
        await message.answer("⚠️ Произошла ошибка при обработке вопроса. Попробуйте позже.")


@dp.message(F.text & F.from_user.id.in_(EXPERT_IDS))
async def handle_expert_text(message: types.Message):
    """Обработка текстовых сообщений от экспертов в режиме редактирования"""

    if message.from_user.id in editing_sessions:
        request_id = editing_sessions[message.from_user.id]
        draft = session.query(DraftAnswer).filter_by(request_id=request_id).first()
        request = session.query(UserRequest).filter_by(id=request_id).first()

        if draft and request:
            # Сохраняем отредактированный текст
            draft.expert_edited_response = message.text
            session.commit()

            # Получаем message_id для редактирования
            message_key = (message.from_user.id, request_id)
            target_message_id = expert_messages.get(message_key)

            # После редактирования возвращаемся к ОСНОВНОЙ клавиатуре
            keyboard = get_expert_keyboard(request_id)  # Стандартная клавиатура!

            # Формируем текст сообщения
            message_text = f"""🆕 Вопрос для модерации (ID: {request_id})

❓ Вопрос пользователя:
{request.question}

🤖 Ответ ИИ (отредактирован):
{message.text}"""

            # Удаляем сообщение с текстом редактирования
            try:
                await message.delete()
            except:
                pass

            # Редактируем сообщение с кнопками
            if target_message_id:
                try:
                    await bot.edit_message_text(
                        chat_id=message.from_user.id,
                        message_id=target_message_id,
                        text=message_text,
                        reply_markup=keyboard  # Стандартная клавиатура
                    )
                except Exception as e:
                    logging.error(f"Ошибка редактирования сообщения: {e}")
                    # Если не удалось отредактировать, отправляем новое
                    await message.answer(
                        message_text,
                        reply_markup=keyboard  # Стандартная клавиатура
                    )
            else:
                await message.answer(
                    message_text,
                    reply_markup=keyboard  # Стандартная клавиатура
                )

            # Удаляем сессию редактирования
            del editing_sessions[message.from_user.id]
            logging.info(f"Эксперт {message.from_user.id} отредактировал ответ на запрос {request_id}")

        else:
            await message.answer("❌ Ошибка: запрос или черновик не найден")
            if message.from_user.id in editing_sessions:
                del editing_sessions[message.from_user.id]
    else:
        # Эксперт пишет обычное сообщение (не в режиме редактирования)
        await message.answer("🤖 Вы эксперт. Используйте кнопки модерации для работы с вопросами.")



# Обработчик нажатия на кнопку "Назад"
@dp.callback_query(F.data.startswith("back_"))
async def back_to_main(callback: types.CallbackQuery):
    """Возврат к меню - НЕ сохраняет несохраненные изменения из текущей сессии"""

    if callback.data in processing_requests:
        await callback.answer("⏳ Запрос уже обрабатывается...", show_alert=True)
        return
    processing_requests.add(callback.data)

    try:
        request_id = int(callback.data.split("_")[1])
        request = session.query(UserRequest).filter_by(id=request_id).first()
        draft = session.query(DraftAnswer).filter_by(request_id=request_id).first()

        if request and draft:
            # Если мы в режиме редактирования (текст еще не сохранен),
            # НЕ используем несохраненные изменения из сессии
            # Просто показываем то, что уже есть в БД

            # Удаляем сессию редактирования (текст не сохранялся)
            if callback.from_user.id in editing_sessions:
                del editing_sessions[callback.from_user.id]

            # Используем сохраненный в БД текст
            current_response = draft.expert_edited_response or draft.llm_response

            # Добавляем пометку если ответ отредактирован
            response_label = "🤖 Ответ ИИ (отредактирован):" if draft.expert_edited_response else "🤖 Ответ ИИ:"

            message_text = f"""🆕 Вопрос для модерации (ID: {request_id})

❓ Вопрос пользователя:
{request.question}

{response_label}
{current_response}"""

            await callback.message.edit_text(
                message_text,
                reply_markup=get_expert_keyboard(request_id)
            )

            await callback.answer("Возврат к основному меню")
        else:
            await callback.answer("❌ Запрос не найден", show_alert=True)

    finally:
        if callback.data in processing_requests:
            processing_requests.remove(callback.data)


async def notify_experts(request_id: int, original_question: str, llm_response: str):
    """Уведомляет экспертов о новом вопросе"""

    request = session.query(UserRequest).filter_by(id=request_id).first()
    if not request:
        logging.error(f"Запрос {request_id} не найден для уведомления экспертов")
        return

    message_text = f"""🆕 Новый вопрос для модерации (ID: {request_id})

👤 Вопрос пользователя:
{original_question}

🤖 Ответ ИИ:
{llm_response}"""

    for expert_id in EXPERT_IDS:
        try:
            message = await bot.send_message(
                expert_id,
                message_text,
                reply_markup=get_expert_keyboard(request_id)
            )
            # Сохраняем message_id для возможности редактирования
            expert_messages[(expert_id, request_id)] = message.message_id

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
            #ВАЖНО: Проверяем, есть ли отредактированный текст ▼▼▼
            if draft.expert_edited_response is not None:
                # Используем отредактированный ответ
                final_response = draft.expert_edited_response
                logging.info(f"Отправляется отредактированный ответ для запроса {request_id}")
            else:
                # Используем оригинальный ответ от ИИ
                final_response = draft.llm_response
                logging.info(f"Отправляется оригинальный ответ ИИ для запроса {request_id}")

            # Обновляем статус
            request.status = 'approved'

            # Добавляем приветствие и дисклеймер
            final_response = giga_client.add_greeting_disclaimer(final_response)

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
                    f"ID запроса: {request_id}\n"
                    f"Тип ответа: {'Отредактированный экспертом' if draft.expert_edited_response else 'Оригинальный от ИИ'}",
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

    if callback.data in processing_requests:
        await callback.answer("⏳ Запрос уже обрабатывается...", show_alert=True)
        return
    processing_requests.add(callback.data)

    try:
        if callback.from_user.id not in EXPERT_IDS:
            await callback.answer("❌ У вас нет прав для редактирования.", show_alert=True)
            return

        request_id = int(callback.data.split("_")[1])
        draft = session.query(DraftAnswer).filter_by(request_id=request_id).first()

        if draft:
            # Сохраняем сессию редактирования
            editing_sessions[callback.from_user.id] = request_id

            # Сохраняем message_id текущего сообщения
            expert_messages[(callback.from_user.id, request_id)] = callback.message.message_id

            current_text = draft.expert_edited_response or draft.llm_response

            cancel_keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="❌ Отменить редактирование", callback_data=f"cancel_edit_{request_id}")],
                [InlineKeyboardButton(text="⬅️ Назад к меню", callback_data=f"back_{request_id}")]
            ])

            # Редактируем текущее сообщение
            await callback.message.edit_text(
                f"✏️ РЕДАКТИРОВАНИЕ (ID запроса: {request_id})\n\n"
                f"Текущий ответ:\n"
                f"────────────────────\n"
                f"{current_text}\n"
                f"────────────────────\n\n"
                f"📝 Пришлите исправленный текст ответа:",
                reply_markup=cancel_keyboard
            )

            await callback.answer("Режим редактирования")
        else:
            await callback.answer("❌ Черновик не найден", show_alert=True)

    finally:
        if callback.data in processing_requests:
            processing_requests.remove(callback.data)


# Обработчик отмены редактирования
@dp.callback_query(F.data.startswith("cancel_edit_"))
async def cancel_editing(callback: types.CallbackQuery):
    """Отмена редактирования - сбрасывает ВСЕ изменения"""

    if callback.data in processing_requests:
        await callback.answer("⏳ Запрос уже обрабатывается...", show_alert=True)
        return
    processing_requests.add(callback.data)

    try:
        request_id = int(callback.data.split("_")[2])

        # Удаляем сессию если существует
        if callback.from_user.id in editing_sessions:
            del editing_sessions[callback.from_user.id]

        request = session.query(UserRequest).filter_by(id=request_id).first()
        draft = session.query(DraftAnswer).filter_by(request_id=request_id).first()

        if request and draft:
            #ВАЖНО: Сбрасываем отредактированный текст в БД!
            draft.expert_edited_response = None
            session.commit()

            # Используем оригинальный текст от ИИ
            current_response = draft.llm_response

            message_text = f"""🆕 Вопрос для модерации (ID: {request_id})

❓ Вопрос пользователя:
{request.question}

🤖 Ответ ИИ:
{current_response}"""

            # Редактируем сообщение обратно к основному виду
            await callback.message.edit_text(
                message_text,
                reply_markup=get_expert_keyboard(request_id)
            )

            await callback.answer("✅ Редактирование отменено, все изменения сброшены")
        else:
            await callback.answer("❌ Запрос не найден", show_alert=True)

    finally:
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

                # Генерируем новый ответ через GigaChat
                new_llm_response = await giga_client.generate_response(request.question)

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

                # Формируем текст сообщения
                message_text = f"""🆕 Новый сгенерированный ответ (ID: {request_id})

❓ Вопрос пользователя:
{request.question}

🤖 Ответ ИИ:
{new_llm_response}"""

                # Обновляем сообщение эксперта с новым ответом
                await callback.message.edit_text(
                    message_text,
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