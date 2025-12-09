import asyncio
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardRemove, InlineKeyboardMarkup, InlineKeyboardButton
import aiohttp  # Правильный импорт
import json
from datetime import datetime

from config import BOT_TOKEN, GIGACHAT_AUTH_KEY, GIGACHAT_SCOPE
from database import session, UserRequest, DraftAnswer
from keyboards import get_expert_keyboard
from gigachat_client import GigaChatClient  # Добавить импорт

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

# Список ID экспертов (замените на реальные ID)
EXPERT_IDS = [982232323]  # Ваш Telegram ID

# Глобальный словарь для отслеживания редактирования
editing_sessions = {}

# Защита от множественных нажатий (anti-flood)
processing_requests = set()

question_processor = QuestionProcessor()




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
    original_question = message.text

    # 1. Обрабатываем вопрос
    processed = question_processor.process_question(original_question)

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


async def notify_experts(request_id: int, original_question: str, llm_response: str):
    """Уведомляет экспертов о новом вопросе"""
    notification_text = f"""
🆕 Новый вопрос для модерации (ID: {request_id})

👤 Вопрос пользователя:
{original_question}

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

            # Добавляем приветствие и дисклеймер
            final_response = giga_client.add_greeting_disclaimer(final_response)  # ← Используем метод из giga_client

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
                f"Текущий ответ:\n"  # Изменили "Текущий текст ответа"
                f"────────────────────\n"
                f"{current_text}\n"
                f"────────────────────\n\n"
                f"📝 Пришлите исправленный текст ответа:\n\n"  # Убрали "СЕЙЧАС"
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
                f"🤖 Ответ ИИ:\n{current_response}",  # Изменили "Текст ответа" на "Ответ ИИ"
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

                # Генерируем новый ответ на ОЧИЩЕННЫЙ вопрос
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

                # Обновляем сообщение эксперта с новым ответом
                await callback.message.edit_text(
                    f"🆕 Новый сгенерированный ответ (ID: {request_id})\n\n"
                    f"❓ Вопрос пользователя:\n{request.question}\n\n"
                    f"🤖 Ответ ИИ:\n{new_llm_response}",  # Изменили "Черновик ответа от ИИ" на "Ответ ИИ"
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