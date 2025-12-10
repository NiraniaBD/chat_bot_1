import logging
import re

logger = logging.getLogger(__name__)


class QuestionProcessor:
    """Умный обработчик вопросов с гибкой фильтрацией"""

    def __init__(self):
        # Приветствия для удаления
        self.greetings = [
            "здравствуйте", "добрый день", "добрый вечер", "доброе утро",
            "привет", "доброй ночи", "уважаемая", "уважаемый"
        ]

        # Обращения (могут быть частью вопроса)
        self.addresses = [
            "татьяна", "николаевна", "татьяна николаевна",
            "администратор", "админ", "доктор", "врач", "специалист",
            "эксперт", "консультант"
        ]

        # Ключевые слова и фразы из реальных вопросов
        self.medical_patterns = [
            # Из примеров
            'вит д', 'витамин д', 'витамин d', 'инъекц', 'укол', 'ампул',
            'схем', 'приём', 'прием', 'прокомментир', 'коммент',
            'ph воды', 'щелочн', 'уровен ph', 'ph питьевой',
            'бад', 'бады', 'биодобав', 'добавк', 'при онкологи',
            'карцином', 'простат', 'пса анализ',
            'vmg+', 'витаминно-минеральн', 'комплекс', 'завтрак',
            'еда', 'пища', 'желудок', 'голодный',
            'ковид', 'covid', 'легк', 'дыхан', 'кашель', 'свист',
            'сатурац', 'ингалятор', 'кортикостероид',
            'пальмов', 'масло', 'состав', 'детск', 'витамин',
            'эфирн', 'масло', 'гастрит', 'слизист', 'раздражат',
            'десн', 'челюст', 'воспал', 'опух', 'стоматолог',
            'иммунитет', 'аллерг', 'чихан', 'слез', 'сонн',
            'кож', 'дермат', 'шершав', 'трещин', 'атопич',
            'бронхит', 'хроническ', 'мокрот', 'эвкалипт', 'ингаляц',
            'остеопороз', 'кальц', 'фтор', 'антипаразитар',
            'миом', 'кист', 'яични', 'папиллом', 'маммолог',
            'геморро', 'шишк', 'боль', 'проктолог',
            'орви', 'фарингит', 'температур', 'горл', 'жаропонижающ',

            # Общие медицинские термины
            'болезн', 'заболеван', 'симптом', 'диагноз', 'лечен',
            'терапи', 'профилактик', 'рекомендац', 'совет',
            'что делать', 'как быть', 'можно ли', 'стоит ли',
            'подскажит', 'посоветуйт', 'помогит', 'объяснит',

            # Частые вопросы о продуктах
            'когда принимат', 'как принимат', 'сколько принимат',
            'с чем принимат', 'до еды', 'после еды', 'во время еды',
            'утром', 'вечером', 'днем', 'на ночь',
            'курс', 'длительн', 'продолжительн', 'перерыв',
            'побочн', 'эффект', 'результат', 'действ',

            # Вопросы о взаимодействии
            'вместе с', 'одновременно', 'параллельн', 'сочета',
            'можно ли совмещат', 'можно ли комбинироват',
            'противопоказан', 'ограничен', 'нельзя',

            # Вопросы о дозировках
            'доз', 'количеств', 'сколько', 'мг', 'мл', 'капель',
            'таблетк', 'капсул', 'ложк', 'чайная', 'столовая',

            # Вопросы о возрасте и состояниях
            'ребенк', 'детск', 'взросл', 'пожил', 'женщин',
            'мужчин', 'беременн', 'кормящ', 'кормление',
            'хроническ', 'острый', 'обострен', 'ремиссия',

            # Вопросы о продуктах/брендах
            'dōterra', 'дотерра', 'young living', 'эфирн масл',
            'продукт компани', 'наша компания', 'ваш продукт'
        ]

        # Паттерны-триггеры (даже одно слово из этих триггеров делает вопрос медицинским)
        self.trigger_patterns = [
            r'(вит|витамин)[\s\.]*[дd]',  # вит Д, витамин Д
            r'инъекц',  # инъекции
            r'ph[\s\-]*вод',  # ph воды
            r'бад(ы|ов)?\b',  # бад, бады
            r'vmg\+',  # VMG+
            r'ковид|covid',  # ковид
            r'эфирн(ое|ые)?\s*масл',  # эфирное масло
            r'гастрит',  # гастрит
            r'иммунитет',  # иммунитет
            r'аллерг',  # аллергия
            r'дермат',  # дерматит
            r'бронхит',  # бронхит
            r'остеопороз',  # остеопороз
            r'миом',  # миома
            r'геморро',  # геморрой
            r'орви',  # ОРВИ
        ]

        # Слова-исключения (точно немедицинские)
        self.non_medical = [
            'политик', 'экономик', 'финанс', 'кредит', 'ипотек',
            'юрист', 'адвокат', 'суд', 'закон', 'прав',
            'религи', 'вера', 'бог', 'церков',
            'кинотеатр', 'концерт', 'выставк', 'музей',
            'ремонт квартир', 'строительств дом',
            'автомобиль купить', 'техника бытов',
            'рецепт пирог', 'блюдо праздничн'
        ]

        # Контекстные фразы, которые указывают на медицинский вопрос
        self.context_phrases = [
            'не могли бы вы', 'прокомментируйте', 'объясните',
            'подскажите пожалуйста', 'посоветуйте',
            'что делать если', 'как быть когда',
            'можно ли принимать', 'стоит ли использовать',
            'какой лучше', 'какая дозировка',
            'чем помочь', 'как справиться',
            'нужны ли исследования', 'к какому врачу'
        ]

    def clean_question(self, question: str) -> str:
        """Очищает вопрос от приветствий, сохраняя суть"""
        original = question
        words = question.split()
        cleaned_words = []

        # Флаг: пропускать ли приветствия (только в начале)
        skip_greetings = True

        for word in words:
            word_lower = word.lower()

            # Удаляем только явные приветствия в начале
            if skip_greetings:
                is_greeting = False
                for greeting in self.greetings:
                    # Приветствие должно быть отдельным словом или в начале
                    if (greeting == word_lower or
                            word_lower.startswith(greeting + ",") or
                            word_lower.startswith(greeting + "!")):
                        is_greeting = True
                        break

                if is_greeting:
                    continue
                else:
                    skip_greetings = False

            # Проверяем, не является ли слово обращением (сохраняем, если оно не отдельное)
            is_address = False
            for address in self.addresses:
                if address == word_lower:
                    is_address = True
                    break

            # Если это отдельное обращение, можно пропустить
            # Но если это "ТатьянаНиколаевна" (слитно), лучше сохранить
            if is_address and len(word_lower) <= 15:  # Только короткие обращения
                continue

            cleaned_words.append(word)

        cleaned = ' '.join(cleaned_words)

        # Если после очистки осталась пустая строка
        if not cleaned.strip():
            return original

        # Убираем начальные/конечные знаки препинания
        cleaned = re.sub(r'^[,\:\-\!\?\s]+', '', cleaned)
        cleaned = re.sub(r'[,\:\-\!\?\s]+$', '', cleaned)

        # Первая буква заглавная
        if cleaned:
            cleaned = cleaned[0].upper() + cleaned[1:]

        logger.debug(f"Очистка: '{original[:50]}...' -> '{cleaned[:50]}...'")
        return cleaned

    def is_health_related(self, question: str) -> bool:
        """Гибкая проверка медицинской тематики"""
        question_lower = question.lower()

        # 1. Проверяем паттерны-триггеры (самый строгий уровень)
        for pattern in self.trigger_patterns:
            if re.search(pattern, question_lower):
                logger.debug(f"Обнаружен триггер-паттерн: {pattern}")
                return True

        # 2. Проверяем контекстные фразы
        has_context = False
        for phrase in self.context_phrases:
            if phrase in question_lower:
                has_context = True
                break

        # 3. Проверяем медицинские паттерны
        medical_score = 0
        for pattern in self.medical_patterns:
            if pattern in question_lower:
                medical_score += 1
                logger.debug(f"Обнаружен медицинский паттерн: {pattern}")

        # 4. Проверяем исключения
        for non_med in self.non_medical:
            if non_med in question_lower:
                # Но если есть сильный медицинский контекст, всё равно медицинский
                if medical_score < 2:  # Слабый медицинский контекст
                    logger.debug(f"Обнаружено немедицинское слово: {non_med}")
                    return False

        # 5. Логика принятия решения

        # Вариант A: Есть контекстная фраза + хотя бы 1 медицинский паттерн
        if has_context and medical_score >= 1:
            logger.debug(f"Принято по правилу A: контекст + паттерн")
            return True

        # Вариант B: Хотя бы 2 медицинских паттерна
        if medical_score >= 2:
            logger.debug(f"Принято по правилу B: {medical_score} паттернов")
            return True

        # Вариант C: Вопрос содержит знак вопроса и медицинские термины
        if '?' in question and medical_score >= 1:
            logger.debug(f"Принято по правилу C: вопрос с медицинским термином")
            return True

        # 6. Специальные случаи из примеров преподавателя
        special_cases = [
            r'#вопрос',  # Хэштег вопроса
            r'вопрос специалисту',  # Явное обращение
            r'подскажите.*пожалуйста',  # Вежливый запрос
            r'посоветуйте.*чем',  # Запрос совета
        ]

        for case in special_cases:
            if re.search(case, question_lower):
                logger.debug(f"Специальный случай: {case}")
                # Даже если мало медицинских терминов, считаем медицинским
                if medical_score >= 1:
                    return True

        logger.debug(f"Вопрос не медицинский: score={medical_score}, context={has_context}")
        return False

    def extract_keywords(self, question: str) -> list:
        """Извлекает ключевые слова из вопроса"""
        question_lower = question.lower()
        keywords = []

        for pattern in self.medical_patterns:
            if pattern in question_lower:
                keywords.append(pattern)

        # Также ищем триггеры
        for pattern in self.trigger_patterns:
            if re.search(pattern, question_lower):
                # Извлекаем найденное слово
                match = re.search(pattern, question_lower)
                if match:
                    keywords.append(match.group())

        return list(set(keywords))  # Убираем дубли

    def process_question(self, question: str) -> dict:
        """Обрабатывает вопрос с расширенной логикой"""
        cleaned = self.clean_question(question)
        is_medical = self.is_health_related(cleaned)
        keywords = self.extract_keywords(cleaned)

        logger.info("=" * 50)
        logger.info(f"Обработка вопроса:")
        logger.info(f"Оригинал: '{question[:100]}...'")
        logger.info(f"Очищенный: '{cleaned[:100]}...'")
        logger.info(f"Медицинский: {is_medical}")
        logger.info(f"Ключевые слова: {keywords}")
        logger.info("=" * 50)

        return {
            "original": question,
            "cleaned": cleaned,
            "is_medical": is_medical,
            "keywords": keywords,
            "error": None if is_medical else "Вопрос не распознан как медицинский"
        }


# Более простой процессор для тестирования
class SimpleQuestionProcessor:
    """Простой процессор для тестирования (альтернатива)"""

    def __init__(self):
        self.medical_indicators = [
            # Все ключевые слова из примеров
            'вит', 'витамин', 'инъекц', 'укол', 'ph', 'щелочн',
            'бад', 'онкологи', 'карцином', 'простат', 'vmg',
            'ковид', 'дыхан', 'кашель', 'эфирн', 'масло',
            'гастрит', 'иммунитет', 'аллерг', 'кож', 'дермат',
            'бронхит', 'остеопороз', 'миом', 'геморро', 'орви',
            'фарингит', 'температур',

            # Общие медицинские
            'болезн', 'заболеван', 'симптом', 'лечен', 'терапи',
            'врач', 'доктор', 'боль', 'дискомфорт',

            # Вопросы
            'что делать', 'как быть', 'можно ли', 'подскажите',
            'посоветуйте', 'объясните', 'прокомментируйте'
        ]

    def is_health_related(self, question: str) -> bool:
        """Очень либеральная проверка"""
        q_lower = question.lower()

        # Если есть хотя бы один медицинский индикатор
        for indicator in self.medical_indicators:
            if indicator in q_lower:
                return True

        # Если вопрос содержит знак вопроса и есть обращения
        if '?' in q_lower and any(word in q_lower for word in ['пожалуйста', 'подскажите', 'посоветуйте']):
            return True

        return False

    def clean_question(self, question: str) -> str:
        """Минимальная очистка"""
        # Убираем только явные приветствия в начале
        greetings = ['здравствуйте', 'добрый день', 'добрый вечер', 'привет']
        words = question.split()

        if words and words[0].lower() in greetings:
            words = words[1:]

        return ' '.join(words).strip()

    def process_question(self, question: str) -> dict:
        cleaned = self.clean_question(question)
        is_medical = self.is_health_related(cleaned)

        return {
            "original": question,
            "cleaned": cleaned,
            "is_medical": is_medical,
            "error": None if is_medical else "Немедицинский вопрос"
        }