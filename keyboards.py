from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

def get_expert_keyboard(request_id: int):
    """Создает клавиатуру для эксперта"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Опубликовать", callback_data=f"approve_{request_id}"),
            InlineKeyboardButton(text="✏️ Редактировать", callback_data=f"edit_{request_id}")
        ],
        [
            InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject_{request_id}")
        ]
    ])
    return keyboard

def get_cancel_keyboard():
    """Клавиатура для отмены действия"""
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="❌ Отмена")]],
        resize_keyboard=True
    )