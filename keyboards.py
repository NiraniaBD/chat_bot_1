from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

def get_expert_keyboard(request_id: int) -> InlineKeyboardMarkup:
    """Стандартная клавиатура для эксперта при модерации"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Опубликовать", callback_data=f"approve_{request_id}"),
            InlineKeyboardButton(text="✏️ Редактировать", callback_data=f"edit_{request_id}")
        ],
        [
            InlineKeyboardButton(text="🔄 Сгенерировать заново", callback_data=f"regenerate_{request_id}"),
            InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject_{request_id}")
        ]
    ])

def get_expert_start_keyboard() -> ReplyKeyboardMarkup:
    """Клавиатура для эксперта после старта"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📋 Показать ожидающие вопросы")],
            [KeyboardButton(text="📊 Статистика"), KeyboardButton(text="🆘 Помощь")]
        ],
        resize_keyboard=True,
        one_time_keyboard=False
    )

def get_user_start_keyboard() -> ReplyKeyboardMarkup:
    """Клавиатура для пользователя после старта"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="❓ Задать вопрос")],
            [KeyboardButton(text="ℹ️ О боте"), KeyboardButton(text="🆘 Помощь")]
        ],
        resize_keyboard=True,
        one_time_keyboard=False
    )

def get_cancel_keyboard():
    """Клавиатура для отмены действия"""
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="❌ Отмена")]],
        resize_keyboard=True
    )