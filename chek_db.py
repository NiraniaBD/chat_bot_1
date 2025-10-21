from database import session, UserRequest, DraftAnswer


def check_database():
    print("📊 Проверка базы данных:")

    # Проверяем вопросы
    requests = session.query(UserRequest).all()
    print(f"📝 Вопросов в базе: {len(requests)}")

    for req in requests:
        print(f"ID: {req.id}, User: {req.user_id}, Status: {req.status}")
        print(f"Question: {req.question[:50]}...")

    # Проверяем черновики
    drafts = session.query(DraftAnswer).all()
    print(f"📄 Черновиков ответов: {len(drafts)}")

    for draft in drafts:
        print(f"Request ID: {draft.request_id}")
        print(f"Response: {draft.llm_response[:50]}...")


if __name__ == "__main__":
    check_database()