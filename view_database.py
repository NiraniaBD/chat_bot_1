from database import session, UserRequest, DraftAnswer
from datetime import datetime


def view_all_data():
    print("=" * 50)
    print("📊 ПРОСМОТР БАЗЫ ДАННЫХ")
    print("=" * 50)

    # Получаем все вопросы
    requests = session.query(UserRequest).order_by(UserRequest.id).all()

    print(f"📝 ВСЕГО ВОПРОСОВ: {len(requests)}")
    print("=" * 50)

    for r in requests:
        status_emoji = "⏳" if r.status == 'waiting' else "✅" if r.status == 'approved' else "❌"
        print(f"{status_emoji} ЗАПРОС ID: {r.id}")
        print(f"   👤 User ID: {r.user_id}")
        print(f"   📊 Статус: {r.status}")
        print(f"   🕒 Время: {r.timestamp}")
        print(f"   ❓ Вопрос: {r.question}")

        # Находим соответствующий черновик
        draft = session.query(DraftAnswer).filter_by(request_id=r.id).first()
        if draft:
            print(f"   🤖 Ответ ИИ: {draft.llm_response[:100]}...")
            if draft.expert_edited_response:
                print(f"   ✏️ Исправленный: {draft.expert_edited_response[:100]}...")
            if draft.expert_id:
                print(f"   👨‍⚕️ Эксперт ID: {draft.expert_id}")
            if draft.decision_time:
                print(f"   ⏱️ Время решения: {draft.decision_time}")
        else:
            print("   ❌ Черновик не найден")

        print("-" * 50)


def view_statistics():
    """Показывает статистику по базе"""
    print("\n📈 СТАТИСТИКА:")
    print("=" * 30)

    total_requests = session.query(UserRequest).count()
    waiting = session.query(UserRequest).filter_by(status='waiting').count()
    approved = session.query(UserRequest).filter_by(status='approved').count()
    rejected = session.query(UserRequest).filter_by(status='rejected').count()

    print(f"Всего запросов: {total_requests}")
    print(f"⏳ Ожидают: {waiting}")
    print(f"✅ Одобрены: {approved}")
    print(f"❌ Отклонены: {rejected}")

    # Самый старый незавершенный запрос
    oldest_waiting = session.query(UserRequest).filter_by(status='waiting').order_by(UserRequest.timestamp).first()
    if oldest_waiting:
        wait_time = datetime.now() - oldest_waiting.timestamp
        print(f"⏰ Самый старый в ожидании: {wait_time.total_seconds() / 60:.1f} минут")


if __name__ == "__main__":
    view_all_data()
    view_statistics()