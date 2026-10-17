from uuid import UUID

from psycopg.errors import UniqueViolation

from app.errors import forbidden, invalid, not_found
from app.schemas import Conversation, Message, MessagePage
from app.services.common import clamp_limit, many, must, notify_many, one, person, require_section
from app.util import decode_cursor, encode_cursor


def _require_chats(conn, user) -> None:
    require_section(conn, "chats")


def _member(conn, conversation_id, user_id):
    row = one(
        conn,
        """
        SELECT c.*, (m.user_id IS NOT NULL) AS is_member
        FROM conversations c
        LEFT JOIN conversation_members m
          ON m.conversation_id = c.id AND m.user_id = %s
        WHERE c.id = %s
        """,
        (user_id, conversation_id),
    )
    row = must(row, "Чат не найден")
    if not row["is_member"]:
        raise not_found("Чат не найден")
    return row


def _open(conversation) -> None:
    if conversation["closed_at"] is not None:
        raise invalid("conversation_closed", "Семестр закрыт, чат доступен только для чтения")


def _message(conn, message_id) -> Message:
    row = must(
        one(
            conn,
            """
            SELECT m.id, m.author_user_id, m.body, m.created_at, m.edited_at, m.deleted_at,
                   u.last_name, u.first_name, u.middle_name
            FROM messages m
            JOIN users u ON u.id = m.author_user_id
            WHERE m.id = %s
            """,
            (message_id,),
        ),
        "Сообщение не найдено",
    )
    attachments = [
        item["file_id"]
        for item in many(
            conn,
            "SELECT file_id FROM message_attachments WHERE message_id = %s",
            (message_id,),
        )
    ]
    deleted = row["deleted_at"] is not None
    return Message(
        id=row["id"],
        author_user_id=row["author_user_id"],
        author_name=person(row),
        body="" if deleted else row["body"],
        created_at=row["created_at"],
        edited_at=row["edited_at"],
        deleted=deleted,
        attachment_ids=[] if deleted else attachments,
    )


def _titles(conn, rows, user_id) -> dict:
    if not rows:
        return {}
    ids = [row["id"] for row in rows]
    titled = many(
        conn,
        """
        SELECT c.id,
               CASE
                   WHEN c.kind = 'group' THEN d.name || ' · ' || g.name
                   ELSE concat_ws(' ', peer.last_name, peer.first_name, NULLIF(peer.middle_name, ''))
                        || ' · ' || d.name
               END AS title
        FROM conversations c
        JOIN disciplines d ON d.id = c.discipline_id
        LEFT JOIN groups g ON g.id = c.group_id
        LEFT JOIN users peer ON peer.id = CASE
            WHEN c.student_user_id = %s THEN c.teacher_user_id
            ELSE c.student_user_id
        END
        WHERE c.id = ANY(%s)
        """,
        (user_id, ids),
    )
    return {row["id"]: row["title"] for row in titled}


def list_conversations(conn, user, query: str | None) -> list[Conversation]:
    _require_chats(conn, user)
    text = (query or "").strip()
    rows = many(
        conn,
        """
        SELECT c.id, c.kind, c.closed_at, c.student_user_id, c.teacher_user_id,
               cm.last_read_at,
               (
                   SELECT count(*)
                   FROM messages m
                   WHERE m.conversation_id = c.id
                     AND m.deleted_at IS NULL
                     AND m.author_user_id <> %s
                     AND (cm.last_read_at IS NULL OR m.created_at > cm.last_read_at)
               ) AS unread_count,
               (
                   SELECT m.id
                   FROM messages m
                   WHERE m.conversation_id = c.id
                   ORDER BY m.created_at DESC
                   LIMIT 1
               ) AS last_id
        FROM conversations c
        JOIN conversation_members cm ON cm.conversation_id = c.id AND cm.user_id = %s
        WHERE (
            %s = ''
            OR EXISTS (
                SELECT 1 FROM messages m
                WHERE m.conversation_id = c.id
                  AND m.deleted_at IS NULL
                  AND to_tsvector('russian', m.body) @@ plainto_tsquery('russian', %s)
            )
        )
        ORDER BY c.created_at DESC
        """,
        (user.id, user.id, text, text),
    )
    titles = _titles(conn, rows, user.id)
    result = []
    for row in rows:
        result.append(
            Conversation(
                id=row["id"],
                kind=row["kind"],
                title=titles.get(row["id"]) or "Чат",
                closed=row["closed_at"] is not None,
                unread_count=row["unread_count"],
                last_message=_message(conn, row["last_id"]) if row["last_id"] else None,
            )
        )
    return result


def create_direct(conn, user, body) -> Conversation:
    _require_chats(conn, user)
    if user.role == "student":
        student_id = user.id
        teacher_id = body.peer_user_id
    elif user.role == "employee":
        teacher_id = user.id
        student_id = body.peer_user_id
    else:
        raise forbidden("Личный чат открывают студент и преподаватель дисциплины")
    link = one(
        conn,
        """
        SELECT 1
        FROM group_disciplines gd
        JOIN student_profiles sp ON sp.group_id = gd.group_id AND sp.user_id = %s
        WHERE gd.discipline_id = %s
          AND gd.semester_id = %s
          AND gd.teacher_user_id = %s
        """,
        (student_id, body.discipline_id, body.semester_id, teacher_id),
    )
    if link is None:
        raise invalid("not_your_teacher", "Личный чат доступен только по дисциплине, которую ведёт этот преподаватель")
    semester = must(one(conn, "SELECT status FROM semesters WHERE id = %s", (body.semester_id,)), "Семестр не найден")
    if semester["status"] == "closed":
        raise invalid("conversation_closed", "Семестр закрыт, новый чат не открывается")
    try:
        with conn.transaction():
            created = conn.execute(
                """
                INSERT INTO conversations (kind, semester_id, discipline_id, student_user_id, teacher_user_id)
                VALUES ('direct', %s, %s, %s, %s)
                RETURNING id
                """,
                (body.semester_id, body.discipline_id, student_id, teacher_id),
            ).fetchone()
            conversation_id = created["id"]
    except UniqueViolation:
        conversation_id = one(
            conn,
            """
            SELECT id FROM conversations
            WHERE kind = 'direct' AND semester_id = %s AND discipline_id = %s
              AND student_user_id = %s AND teacher_user_id = %s
            """,
            (body.semester_id, body.discipline_id, student_id, teacher_id),
        )["id"]
    for member_id in (student_id, teacher_id):
        conn.execute(
            """
            INSERT INTO conversation_members (conversation_id, user_id)
            VALUES (%s, %s)
            ON CONFLICT DO NOTHING
            """,
            (conversation_id, member_id),
        )
    return _one_conversation(conn, user, conversation_id)


def _one_conversation(conn, user, conversation_id) -> Conversation:
    found = one(
        conn,
        """
        SELECT c.id, c.kind, c.closed_at,
               (
                   SELECT count(*)
                   FROM messages m
                   JOIN conversation_members cm ON cm.conversation_id = c.id AND cm.user_id = %s
                   WHERE m.conversation_id = c.id
                     AND m.deleted_at IS NULL
                     AND m.author_user_id <> %s
                     AND (cm.last_read_at IS NULL OR m.created_at > cm.last_read_at)
               ) AS unread_count,
               (
                   SELECT m.id FROM messages m
                   WHERE m.conversation_id = c.id
                   ORDER BY m.created_at DESC LIMIT 1
               ) AS last_id
        FROM conversations c
        WHERE c.id = %s
        """,
        (user.id, user.id, conversation_id),
    )
    titles = _titles(conn, [found], user.id)
    return Conversation(
        id=found["id"],
        kind=found["kind"],
        title=titles.get(found["id"]) or "Чат",
        closed=found["closed_at"] is not None,
        unread_count=found["unread_count"],
        last_message=_message(conn, found["last_id"]) if found["last_id"] else None,
    )


def list_messages(conn, user, conversation_id, cursor: str | None, limit: int | None) -> MessagePage:
    _require_chats(conn, user)
    _member(conn, conversation_id, user.id)
    size = clamp_limit(limit)
    params: list = [conversation_id]
    clause = ""
    if cursor:
        moment, entity_id = decode_cursor(cursor)
        clause = "AND (m.created_at, m.id) < (%s, %s)"
        params.extend([moment, entity_id])
    params.append(size + 1)
    rows = many(
        conn,
        f"""
        SELECT m.id
        FROM messages m
        WHERE m.conversation_id = %s {clause}
        ORDER BY m.created_at DESC, m.id DESC
        LIMIT %s
        """,
        tuple(params),
    )
    next_cursor = None
    if len(rows) > size:
        rows = rows[:size]
        oldest = one(conn, "SELECT created_at FROM messages WHERE id = %s", (rows[-1]["id"],))
        next_cursor = encode_cursor(oldest["created_at"], rows[-1]["id"])
    items = [_message(conn, row["id"]) for row in reversed(rows)]
    return MessagePage(items=items, next_cursor=next_cursor)


def create_message(conn, user, conversation_id, body) -> Message:
    _require_chats(conn, user)
    conversation = _member(conn, conversation_id, user.id)
    _open(conversation)
    text = body.body.strip()
    if not text and not body.attachment_ids:
        raise invalid("empty_message", "Напишите текст или приложите файл")
    if len(text) > 4000:
        raise invalid("message_too_long", "Сообщение длиннее 4000 символов")
    existing = one(
        conn,
        """
        SELECT id FROM messages
        WHERE conversation_id = %s AND client_message_id = %s
        """,
        (conversation_id, body.client_message_id),
    )
    if existing:
        return _message(conn, existing["id"])
    for file_id in body.attachment_ids:
        owned = one(
            conn,
            "SELECT 1 FROM files WHERE id = %s AND uploaded_by = %s",
            (file_id, user.id),
        )
        if owned is None:
            raise invalid("attachment_rejected", "Можно приложить только свой файл")
    try:
        with conn.transaction():
            created = conn.execute(
                """
                INSERT INTO messages (conversation_id, author_user_id, client_message_id, body)
                VALUES (%s, %s, %s, %s)
                RETURNING id
                """,
                (conversation_id, user.id, body.client_message_id, text),
            ).fetchone()
    except UniqueViolation:
        existing = one(
            conn,
            """
            SELECT id FROM messages
            WHERE conversation_id = %s AND client_message_id = %s
            """,
            (conversation_id, body.client_message_id),
        )
        return _message(conn, existing["id"])
    for file_id in body.attachment_ids:
        conn.execute(
            "INSERT INTO message_attachments (message_id, file_id) VALUES (%s, %s)",
            (created["id"], file_id),
        )
    members = many(
        conn,
        "SELECT user_id FROM conversation_members WHERE conversation_id = %s AND user_id <> %s",
        (conversation_id, user.id),
    )
    notify_many(
        conn,
        [row["user_id"] for row in members],
        "message",
        "Новое сообщение",
        text[:140],
        {"conversationId": str(conversation_id), "messageId": str(created["id"])},
    )
    return _message(conn, created["id"])


def update_message(conn, user, message_id: UUID, text: str) -> Message:
    _require_chats(conn, user)
    row = must(one(conn, "SELECT * FROM messages WHERE id = %s", (message_id,)), "Сообщение не найдено")
    conversation = _member(conn, row["conversation_id"], user.id)
    _open(conversation)
    if row["author_user_id"] != user.id or row["deleted_at"] is not None:
        raise forbidden("Можно изменить только своё сообщение")
    cleaned = text.strip()
    if not cleaned:
        raise invalid("empty_message", "Текст сообщения пустой")
    conn.execute(
        "UPDATE messages SET body = %s, edited_at = now() WHERE id = %s",
        (cleaned, message_id),
    )
    return _message(conn, message_id)


def delete_message(conn, user, message_id: UUID) -> None:
    _require_chats(conn, user)
    row = must(one(conn, "SELECT * FROM messages WHERE id = %s", (message_id,)), "Сообщение не найдено")
    conversation = _member(conn, row["conversation_id"], user.id)
    _open(conversation)
    if row["author_user_id"] != user.id:
        raise forbidden("Можно удалить только своё сообщение")
    conn.execute("UPDATE messages SET deleted_at = now() WHERE id = %s AND deleted_at IS NULL", (message_id,))


def mark_read(conn, user, conversation_id, message_id) -> None:
    _require_chats(conn, user)
    _member(conn, conversation_id, user.id)
    message = must(
        one(
            conn,
            "SELECT id, created_at FROM messages WHERE id = %s AND conversation_id = %s",
            (message_id, conversation_id),
        ),
        "Сообщение не найдено",
    )
    conn.execute(
        """
        UPDATE conversation_members
        SET last_read_message_id = %s, last_read_at = %s
        WHERE conversation_id = %s AND user_id = %s
        """,
        (message["id"], message["created_at"], conversation_id, user.id),
    )
