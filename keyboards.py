from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

# keyboards.py
def get_expert_keyboard(request_id: int) -> InlineKeyboardMarkup:
    """Стандартная клавиатура для эксперта"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Опубликовать", callback_data=f"approve_{request_id}"),
            InlineKeyboardButton(text="✏️ Редактировать", callback_data=f"edit_{request_id}")
        ],
        [
            InlineKeyboardButton(text="🔄 Сгенерировать заново", callback_data=f"regenerate_{request_id}"),
            InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject_{request_id}")  # ← Кнопка "Отклонить" здесь!
        ]
    ])

def get_cancel_keyboard():
    """Клавиатура для отмены действия"""
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="❌ Отмена")]],
        resize_keyboard=True
    )