# question_processor.py
import logging

logger = logging.getLogger(__name__)


class QuestionProcessor:
    """Обработчик вопросов: очистка и проверка тематики"""

    def __init__(self):
        self.greetings = [
            "здравствуйте", "добрый день", "добрый вечер", "доброе утро",
            "привет", "доброй ночи", "татьяна", "николаевна", "татьяна николаевна",
            "уважаемая", "уважаемый", "администратор", "админ"
        ]

        self.health_keywords = [
            # Симптомы и боли
            'болит', 'боль', 'симптом', 'кашель', 'насморк', 'температур', 'жар', 'озноб',
            'тошнит', 'рвота', 'понос', 'запор', 'головокружени', 'слабость', 'усталост',
            'зуд', 'сып', 'покраснен', 'отек', 'опухол', 'воспален',
            # ... и так далее ...
        ]

    def clean_question(self, question: str) -> str:
        """Очищает вопрос от приветствий и обращений"""
        words = question.lower().split()
        cleaned_words = []
        skip_greetings = True

        for word in words:
            is_greeting = any(greeting in word for greeting in self.greetings)
            if skip_greetings and is_greeting:
                continue
            else:
                cleaned_words.append(word)
                skip_greetings = False

        cleaned_question = ' '.join(cleaned_words)
        if not cleaned_question.strip():
            return question

        cleaned_question = cleaned_question[0].upper() + cleaned_question[1:]
        return cleaned_question

    def is_health_related(self, question: str) -> bool:
        """Проверяет, относится ли вопрос к здоровью"""
        question_lower = question.lower()

        # Проверка по ключевым словам
        for keyword in self.health_keywords:
            if keyword in question_lower:
                return True

        # Проверка по контексту
        if 'что делать при' in question_lower or 'что делать если' in question_lower:
            return True

        if 'как лечить' in question_lower or 'чем лечить' in question_lower:
            return True

        # Проверка на медицинские вопросы
        medical_phrases = [
            'что делать при', 'что делать если', 'как лечить', 'чем лечить',
            'симптомы', 'причины', 'профилактика', 'лечение', 'диагностика'
        ]

        for phrase in medical_phrases:
            if phrase in question_lower:
                return True

        return False

    def process_question(self, question: str) -> dict:
        """Обрабатывает вопрос и возвращает результат"""
        cleaned = self.clean_question(question)
        is_medical = self.is_health_related(cleaned)

        logger.info(f"Обработка вопроса: '{question}'")
        logger.info(f"Очищенный: '{cleaned}'")
        logger.info(f"Медицинский: {is_medical}")

        return {
            "original": question,
            "cleaned": cleaned,
            "is_medical": is_medical,
            "error": None if is_medical else "Немедицинский вопрос"
        }