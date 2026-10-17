from decimal import Decimal

from psycopg.errors import UniqueViolation
from psycopg.types.json import Json

from app.errors import forbidden, invalid
from app.schemas import (
    AdminUser,
    AuditEvent,
    AuditPage,
    ChatSyncResult,
    Contract,
    CurriculumItem,
    Discipline,
    ElectiveBlock,
    LedgerEntry,
    OrgUnit,
    PermissionInfo,
    ProfileCorrection,
    RatingFormula,
    ScholarshipGrant,
    ScholarshipPayout,
    Semester,
    StudyGroup,
    UniversitySettings,
    UserPage,
)
from app.security import hash_password
from app.services.common import (
    audit,
    blank,
    clamp_limit,
    load_university,
    many,
    must,
    notify,
    one,
    parse_amount,
    person,
    settings_university,
)
from app.services.desk import _contract, _ledger
from app.services.rating import recompute_student
from app.services.schedule import fetch_lesson, lesson_model, notify_schedule, replace_lesson_groups
from app.util import decimal_str, decode_cursor, encode_cursor, money


def get_settings(conn, user) -> UniversitySettings:
    user.require("settings.manage")
    return settings_university(load_university(conn))


def update_settings(conn, user, body) -> UniversitySettings:
    user.require("settings.manage")
    current = load_university(conn)
    data = body.model_dump(exclude_unset=True)
    if "pass_score" in data and data["pass_score"] is not None:
        data["pass_score"] = parse_amount(data["pass_score"], allow_zero=True)
    if "logo_file_id" in data and data["logo_file_id"] is not None:
        must(one(conn, "SELECT 1 FROM files WHERE id = %s", (data["logo_file_id"],)), "Файл логотипа не найден")
    columns = {
        "name": "name",
        "short_name": "short_name",
        "brand_seed": "brand_seed",
        "brand_accent": "brand_accent",
        "enabled_sections": "enabled_sections",
        "timezone": "timezone",
        "student_match_field": "student_match_field",
        "pass_score": "pass_score",
        "failing_labels": "failing_labels",
        "logo_file_id": "logo_file_id",
    }
    assignments = []
    values = []
    for key, column in columns.items():
        if key in data:
            assignments.append(f"{column} = %s")
            values.append(data[key])
    if assignments:
        values.append(1)
        conn.execute(f"UPDATE university SET {', '.join(assignments)} WHERE id = %s", tuple(values))
    audit(conn, user.id, "university.update", "university", "1", {"fields": list(data)})
    return settings_university(load_university(conn))


def list_org_units(conn, user) -> list[OrgUnit]:
    user.require("settings.manage")
    return [
        OrgUnit(id=row["id"], parent_id=row["parent_id"], kind=row["kind"], name=row["name"])
        for row in many(conn, "SELECT id, parent_id, kind, name FROM org_units ORDER BY name")
    ]


def create_org_unit(conn, user, body) -> OrgUnit:
    user.require("settings.manage")
    row = conn.execute(
        """
        INSERT INTO org_units (parent_id, kind, name)
        VALUES (%s, %s, %s)
        RETURNING id, parent_id, kind, name
        """,
        (body.parent_id, body.kind, body.name.strip()),
    ).fetchone()
    audit(conn, user.id, "org_unit.create", "org_unit", row["id"])
    return OrgUnit(**row)


def update_org_unit(conn, user, org_id, body) -> OrgUnit:
    user.require("settings.manage")
    must(one(conn, "SELECT 1 FROM org_units WHERE id = %s", (org_id,)))
    row = conn.execute(
        """
        UPDATE org_units SET parent_id = %s, kind = %s, name = %s
        WHERE id = %s
        RETURNING id, parent_id, kind, name
        """,
        (body.parent_id, body.kind, body.name.strip(), org_id),
    ).fetchone()
    audit(conn, user.id, "org_unit.update", "org_unit", org_id)
    return OrgUnit(**row)


def _semester(row) -> Semester:
    return Semester(
        id=row["id"],
        title=row["title"],
        starts_on=row["starts_on"],
        ends_on=row["ends_on"],
        status=row["status"],
        elective_open_on=row["elective_open_on"],
        elective_close_on=row["elective_close_on"],
        elective_change_until=row["elective_change_until"],
    )


def list_semesters(conn, user) -> list[Semester]:
    user.require("settings.manage")
    return [_semester(row) for row in many(conn, "SELECT * FROM semesters ORDER BY starts_on DESC")]


def create_semester(conn, user, body) -> Semester:
    user.require("settings.manage")
    row = conn.execute(
        """
        INSERT INTO semesters (
            title, starts_on, ends_on, status, elective_open_on, elective_close_on, elective_change_until
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        RETURNING *
        """,
        (
            body.title.strip(),
            body.starts_on,
            body.ends_on,
            body.status,
            body.elective_open_on,
            body.elective_close_on,
            body.elective_change_until,
        ),
    ).fetchone()
    audit(conn, user.id, "semester.create", "semester", row["id"])
    return _semester(row)


def update_semester(conn, user, semester_id, body) -> Semester:
    user.require("settings.manage")
    must(one(conn, "SELECT 1 FROM semesters WHERE id = %s", (semester_id,)))
    row = conn.execute(
        """
        UPDATE semesters
        SET title = %s, starts_on = %s, ends_on = %s, status = %s,
            elective_open_on = %s, elective_close_on = %s, elective_change_until = %s
        WHERE id = %s
        RETURNING *
        """,
        (
            body.title.strip(),
            body.starts_on,
            body.ends_on,
            body.status,
            body.elective_open_on,
            body.elective_close_on,
            body.elective_change_until,
            semester_id,
        ),
    ).fetchone()
    audit(conn, user.id, "semester.update", "semester", semester_id)
    return _semester(row)


def sync_chats(conn, user, semester_id) -> ChatSyncResult:
    user.require("schedule.manage")
    must(one(conn, "SELECT 1 FROM semesters WHERE id = %s", (semester_id,)), "Семестр не найден")
    rows = many(
        conn,
        """
        SELECT l.discipline_id, lg.group_id, l.teacher_user_id
        FROM lessons l
        JOIN lesson_groups lg ON lg.lesson_id = l.id
        WHERE l.semester_id = %s
          AND l.publication_status = 'published'
          AND l.cancelled_at IS NULL
        """,
        (semester_id,),
    )
    created = 0
    added = 0
    seen: set[tuple] = set()
    teachers: dict[tuple, set] = {}
    for row in rows:
        key = (row["discipline_id"], row["group_id"])
        seen.add(key)
        if row["teacher_user_id"]:
            teachers.setdefault(key, set()).add(row["teacher_user_id"])
    for discipline_id, group_id in seen:
        existing = one(
            conn,
            """
            SELECT id FROM conversations
            WHERE kind = 'group' AND semester_id = %s AND discipline_id = %s AND group_id = %s
            """,
            (semester_id, discipline_id, group_id),
        )
        if existing is None:
            existing = conn.execute(
                """
                INSERT INTO conversations (kind, semester_id, discipline_id, group_id)
                VALUES ('group', %s, %s, %s)
                RETURNING id
                """,
                (semester_id, discipline_id, group_id),
            ).fetchone()
            created += 1
        conversation_id = existing["id"]
        member_ids = [
            row["user_id"]
            for row in many(
                conn,
                "SELECT user_id FROM student_profiles WHERE group_id = %s",
                (group_id,),
            )
        ]
        member_ids.extend(teachers.get((discipline_id, group_id), ()))
        for member_id in member_ids:
            inserted = conn.execute(
                """
                INSERT INTO conversation_members (conversation_id, user_id)
                VALUES (%s, %s)
                ON CONFLICT DO NOTHING
                """,
                (conversation_id, member_id),
            )
            added += inserted.rowcount
    audit(conn, user.id, "semester.sync_chats", "semester", semester_id, {"created": created, "added": added})
    return ChatSyncResult(conversations_created=created, members_added=added)


def close_semester(conn, user, semester_id) -> Semester:
    user.require("settings.manage")
    must(one(conn, "SELECT 1 FROM semesters WHERE id = %s", (semester_id,)), "Семестр не найден")
    conn.execute("UPDATE semesters SET status = 'closed' WHERE id = %s", (semester_id,))
    conn.execute(
        """
        UPDATE conversations
        SET closed_at = COALESCE(closed_at, now())
        WHERE semester_id = %s
        """,
        (semester_id,),
    )
    audit(conn, user.id, "semester.close", "semester", semester_id)
    return _semester(must(one(conn, "SELECT * FROM semesters WHERE id = %s", (semester_id,))))


def list_groups(conn, user) -> list[StudyGroup]:
    user.require("settings.manage")
    return [
        StudyGroup(id=row["id"], org_unit_id=row["org_unit_id"], name=row["name"], course=row["course"], entry_year=row["entry_year"])
        for row in many(conn, "SELECT * FROM groups ORDER BY entry_year DESC, name")
    ]


def create_group(conn, user, body) -> StudyGroup:
    user.require("settings.manage")
    row = conn.execute(
        """
        INSERT INTO groups (org_unit_id, name, course, entry_year)
        VALUES (%s, %s, %s, %s)
        RETURNING *
        """,
        (body.org_unit_id, body.name.strip(), body.course, body.entry_year),
    ).fetchone()
    audit(conn, user.id, "group.create", "group", row["id"])
    return StudyGroup(id=row["id"], org_unit_id=row["org_unit_id"], name=row["name"], course=row["course"], entry_year=row["entry_year"])


def update_group(conn, user, group_id, body) -> StudyGroup:
    user.require("settings.manage")
    row = must(
        conn.execute(
            """
            UPDATE groups SET org_unit_id = %s, name = %s, course = %s, entry_year = %s
            WHERE id = %s RETURNING *
            """,
            (body.org_unit_id, body.name.strip(), body.course, body.entry_year, group_id),
        ).fetchone()
    )
    audit(conn, user.id, "group.update", "group", group_id)
    return StudyGroup(id=row["id"], org_unit_id=row["org_unit_id"], name=row["name"], course=row["course"], entry_year=row["entry_year"])


def list_disciplines(conn, user) -> list[Discipline]:
    user.require("settings.manage")
    return [
        Discipline(id=row["id"], code=row["code"], name=row["name"], org_unit_id=row["org_unit_id"])
        for row in many(conn, "SELECT * FROM disciplines ORDER BY code")
    ]


def create_discipline(conn, user, body) -> Discipline:
    user.require("settings.manage")
    row = conn.execute(
        "INSERT INTO disciplines (code, name, org_unit_id) VALUES (%s, %s, %s) RETURNING *",
        (body.code.strip(), body.name.strip(), body.org_unit_id),
    ).fetchone()
    audit(conn, user.id, "discipline.create", "discipline", row["id"])
    return Discipline(id=row["id"], code=row["code"], name=row["name"], org_unit_id=row["org_unit_id"])


def update_discipline(conn, user, discipline_id, body) -> Discipline:
    user.require("settings.manage")
    row = must(
        conn.execute(
            """
            UPDATE disciplines SET code = %s, name = %s, org_unit_id = %s
            WHERE id = %s RETURNING *
            """,
            (body.code.strip(), body.name.strip(), body.org_unit_id, discipline_id),
        ).fetchone()
    )
    audit(conn, user.id, "discipline.update", "discipline", discipline_id)
    return Discipline(id=row["id"], code=row["code"], name=row["name"], org_unit_id=row["org_unit_id"])


def list_blocks(conn, user, semester_id, group_id) -> list[ElectiveBlock]:
    user.require("settings.manage")
    filters = []
    params = []
    if semester_id:
        filters.append("semester_id = %s")
        params.append(semester_id)
    if group_id:
        filters.append("group_id = %s")
        params.append(group_id)
    where = f"WHERE {' AND '.join(filters)}" if filters else ""
    return [
        ElectiveBlock(id=row["id"], group_id=row["group_id"], semester_id=row["semester_id"], title=row["title"])
        for row in many(conn, f"SELECT * FROM elective_blocks {where} ORDER BY title", tuple(params))
    ]


def create_block(conn, user, body) -> ElectiveBlock:
    user.require("settings.manage")
    row = conn.execute(
        """
        INSERT INTO elective_blocks (group_id, semester_id, title)
        VALUES (%s, %s, %s) RETURNING *
        """,
        (body.group_id, body.semester_id, body.title.strip()),
    ).fetchone()
    audit(conn, user.id, "elective_block.create", "elective_block", row["id"])
    return ElectiveBlock(id=row["id"], group_id=row["group_id"], semester_id=row["semester_id"], title=row["title"])


def _credits(value: str | None) -> Decimal:
    text = (value or "0").strip()
    try:
        amount = Decimal(text)
    except Exception as exc:
        raise invalid("bad_credits", "Кредиты записаны не числом") from exc
    if amount < 0:
        raise invalid("bad_credits", "Кредиты не бывают отрицательными")
    return amount.quantize(Decimal("0.1"))


def list_curriculum(conn, user, semester_id, group_id) -> list[CurriculumItem]:
    user.require("settings.manage")
    filters = []
    params = []
    if semester_id:
        filters.append("semester_id = %s")
        params.append(semester_id)
    if group_id:
        filters.append("group_id = %s")
        params.append(group_id)
    where = f"WHERE {' AND '.join(filters)}" if filters else ""
    return [
        CurriculumItem(
            id=row["id"],
            group_id=row["group_id"],
            discipline_id=row["discipline_id"],
            semester_id=row["semester_id"],
            kind=row["kind"],
            credits=decimal_str(row["credits"], "0.1"),
            teacher_user_id=row["teacher_user_id"],
            elective_block_id=row["elective_block_id"],
        )
        for row in many(conn, f"SELECT * FROM group_disciplines {where} ORDER BY created_at", tuple(params))
    ]


def create_curriculum(conn, user, body) -> CurriculumItem:
    user.require("settings.manage")
    if body.kind == "elective" and body.elective_block_id is None:
        raise invalid("block_required", "Для выборной дисциплины укажите блок")
    if body.kind == "required" and body.elective_block_id is not None:
        raise invalid("block_forbidden", "У обязательной дисциплины блока нет")
    row = conn.execute(
        """
        INSERT INTO group_disciplines (
            group_id, discipline_id, semester_id, kind, elective_block_id, credits, teacher_user_id
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        RETURNING *
        """,
        (
            body.group_id,
            body.discipline_id,
            body.semester_id,
            body.kind,
            body.elective_block_id,
            _credits(body.credits),
            body.teacher_user_id,
        ),
    ).fetchone()
    audit(conn, user.id, "curriculum.create", "group_discipline", row["id"])
    return CurriculumItem(
        id=row["id"],
        group_id=row["group_id"],
        discipline_id=row["discipline_id"],
        semester_id=row["semester_id"],
        kind=row["kind"],
        credits=decimal_str(row["credits"], "0.1"),
        teacher_user_id=row["teacher_user_id"],
        elective_block_id=row["elective_block_id"],
    )


def list_admin_lessons(conn, user, semester_id, group_id) -> list:
    user.require("schedule.manage")
    filters = ["TRUE"]
    params: list = []
    if semester_id:
        filters.append("l.semester_id = %s")
        params.append(semester_id)
    if group_id:
        filters.append(
            "EXISTS (SELECT 1 FROM lesson_groups lgf WHERE lgf.lesson_id = l.id AND lgf.group_id = %s)"
        )
        params.append(group_id)
    from app.services.schedule import _lesson_sql

    return [lesson_model(row) for row in many(conn, _lesson_sql(" AND ".join(filters)), tuple(params))]


def create_lesson(conn, user, body):
    user.require("schedule.manage")
    if not body.group_ids:
        raise invalid("groups_required", "У пары должна быть хотя бы одна группа")
    row = conn.execute(
        """
        INSERT INTO lessons (
            semester_id, discipline_id, teacher_user_id, starts_at, ends_at, room, note
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        RETURNING id
        """,
        (
            body.semester_id,
            body.discipline_id,
            body.teacher_user_id,
            body.starts_at,
            body.ends_at,
            body.room,
            body.note,
        ),
    ).fetchone()
    replace_lesson_groups(conn, row["id"], body.group_ids)
    audit(conn, user.id, "lesson.create", "lesson", row["id"])
    return lesson_model(must(fetch_lesson(conn, row["id"])))


def update_lesson(conn, user, lesson_id, body):
    user.require("schedule.manage")
    current = must(fetch_lesson(conn, lesson_id), "Пара не найдена")
    if not body.group_ids:
        raise invalid("groups_required", "У пары должна быть хотя бы одна группа")
    cancelled_at = current["cancelled_at"]
    if body.cancelled is True and cancelled_at is None:
        cancelled_at = conn.execute("SELECT now() AS at").fetchone()["at"]
    elif body.cancelled is False:
        cancelled_at = None
    conn.execute(
        """
        UPDATE lessons
        SET semester_id = %s, discipline_id = %s, teacher_user_id = %s,
            starts_at = %s, ends_at = %s, room = %s, note = %s, cancelled_at = %s
        WHERE id = %s
        """,
        (
            body.semester_id,
            body.discipline_id,
            body.teacher_user_id,
            body.starts_at,
            body.ends_at,
            body.room,
            body.note,
            cancelled_at,
            lesson_id,
        ),
    )
    replace_lesson_groups(conn, lesson_id, body.group_ids)
    if current["publication_status"] == "published":
        notify_schedule(conn, lesson_id, "Пара в расписании изменилась")
    audit(conn, user.id, "lesson.update", "lesson", lesson_id)
    return lesson_model(must(fetch_lesson(conn, lesson_id)))


def publish_lesson(conn, user, lesson_id):
    user.require("schedule.manage")
    must(fetch_lesson(conn, lesson_id), "Пара не найдена")
    conn.execute(
        """
        UPDATE lessons
        SET publication_status = 'published', published_at = COALESCE(published_at, now())
        WHERE id = %s
        """,
        (lesson_id,),
    )
    notify_schedule(conn, lesson_id, "В расписании новая пара")
    audit(conn, user.id, "lesson.publish", "lesson", lesson_id)
    return lesson_model(must(fetch_lesson(conn, lesson_id)))


def _user_row(conn, user_id) -> AdminUser:
    row = must(
        one(
            conn,
            """
            SELECT u.id, u.role, u.status, u.last_name, u.first_name, u.middle_name,
                   u.login, u.email, u.phone, u.created_at,
                   COALESCE(array_agg(p.permission_code) FILTER (WHERE p.permission_code IS NOT NULL), '{}') AS permissions
            FROM users u
            LEFT JOIN user_permissions p ON p.user_id = u.id
            WHERE u.id = %s
            GROUP BY u.id
            """,
            (user_id,),
        ),
        "Пользователь не найден",
    )
    return AdminUser(
        id=row["id"],
        role=row["role"],
        status=row["status"],
        last_name=row["last_name"],
        first_name=row["first_name"],
        middle_name=row["middle_name"],
        login=row["login"],
        email=row["email"],
        phone=row["phone"],
        permissions=list(row["permissions"]),
    )


def list_users(conn, user, query: str | None, role: str | None, status: str | None, cursor: str | None, limit: int | None) -> UserPage:
    user.require("users.manage")
    size = clamp_limit(limit)
    filters = ["TRUE"]
    params: list = []
    if role:
        filters.append("u.role = %s")
        params.append(role)
    if status:
        filters.append("u.status = %s")
        params.append(status)
    if query and query.strip():
        needle = f"%{query.strip()}%"
        folded = f"%{query.strip().lower().replace('ё', 'е')}%"
        filters.append(
            """(
                u.login ILIKE %s OR u.email::text ILIKE %s OR COALESCE(u.phone, '') ILIKE %s
                OR u.name_key LIKE %s
                OR EXISTS (
                    SELECT 1 FROM student_profiles sp
                    WHERE sp.user_id = u.id
                      AND (COALESCE(sp.student_card_number, '') ILIKE %s
                           OR COALESCE(sp.record_book_number, '') ILIKE %s)
                )
            )"""
        )
        params.extend([needle, needle, needle, folded, needle, needle])
    if cursor:
        moment, entity_id = decode_cursor(cursor)
        filters.append("(u.created_at, u.id) < (%s, %s)")
        params.extend([moment, entity_id])
    params.append(size + 1)
    rows = many(
        conn,
        f"""
        SELECT u.id
        FROM users u
        WHERE {' AND '.join(filters)}
        ORDER BY u.created_at DESC, u.id DESC
        LIMIT %s
        """,
        tuple(params),
    )
    next_cursor = None
    if len(rows) > size:
        rows = rows[:size]
        stamp = one(conn, "SELECT created_at FROM users WHERE id = %s", (rows[-1]["id"],))
        next_cursor = encode_cursor(stamp["created_at"], rows[-1]["id"])
    return UserPage(items=[_user_row(conn, row["id"]) for row in rows], next_cursor=next_cursor)


def _replace_permissions(conn, user_id, codes: list[str]) -> None:
    conn.execute("DELETE FROM user_permissions WHERE user_id = %s", (user_id,))
    for code in dict.fromkeys(codes):
        conn.execute(
            "INSERT INTO user_permissions (user_id, permission_code) VALUES (%s, %s)",
            (user_id, code),
        )


def create_user(conn, user, body) -> AdminUser:
    user.require("users.manage")
    if len(body.password) < 8:
        raise invalid("weak_password", "Пароль должен быть не короче 8 символов")
    try:
        with conn.transaction():
            created = conn.execute(
                """
                INSERT INTO users (role, status, last_name, first_name, middle_name, login, email, phone, password_hash)
                VALUES (%s, 'active', %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    body.role,
                    body.last_name.strip(),
                    body.first_name.strip(),
                    body.middle_name.strip(),
                    body.login.strip(),
                    blank(body.email),
                    blank(body.phone),
                    hash_password(body.password),
                ),
            ).fetchone()
            if body.role == "employee":
                conn.execute(
                    """
                    INSERT INTO employee_profiles (user_id, org_unit_id, position)
                    VALUES (%s, %s, %s)
                    """,
                    (created["id"], body.org_unit_id, body.position),
                )
            _replace_permissions(conn, created["id"], body.permissions)
    except UniqueViolation as exc:
        raise invalid("login_taken", "Логин, почта или телефон уже заняты") from exc
    audit(conn, user.id, "user.create", "user", created["id"])
    return _user_row(conn, created["id"])


def update_user(conn, user, user_id, body) -> AdminUser:
    user.require("users.manage")
    current = must(one(conn, "SELECT * FROM users WHERE id = %s", (user_id,)))
    sent = body.model_fields_set
    password_hash = current["password_hash"]
    password_changed = False
    if "password" in sent and body.password:
        if len(body.password) < 8:
            raise invalid("weak_password", "Пароль должен быть не короче 8 символов")
        password_hash = hash_password(body.password)
        password_changed = True
    middle = body.middle_name.strip() if "middle_name" in sent else current["middle_name"]
    email = blank(body.email) if "email" in sent else current["email"]
    phone = blank(body.phone) if "phone" in sent else current["phone"]
    try:
        with conn.transaction():
            conn.execute(
                """
                UPDATE users
                SET last_name = %s, first_name = %s, middle_name = %s,
                    login = %s, email = %s, phone = %s, password_hash = %s
                WHERE id = %s
                """,
                (
                    body.last_name.strip(),
                    body.first_name.strip(),
                    middle,
                    body.login.strip(),
                    email,
                    phone,
                    password_hash,
                    user_id,
                ),
            )
            if current["role"] == "employee" and {"position", "org_unit_id"} & sent:
                profile_row = one(conn, "SELECT org_unit_id, position FROM employee_profiles WHERE user_id = %s", (user_id,))
                org_id = body.org_unit_id if "org_unit_id" in sent else (profile_row["org_unit_id"] if profile_row else None)
                if "position" in sent and body.position is not None:
                    position = body.position
                else:
                    position = profile_row["position"] if profile_row else ""
                conn.execute(
                    """
                    INSERT INTO employee_profiles (user_id, org_unit_id, position)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (user_id) DO UPDATE
                    SET org_unit_id = EXCLUDED.org_unit_id, position = EXCLUDED.position
                    """,
                    (user_id, org_id, position),
                )
            if "permissions" in sent and body.permissions is not None:
                _replace_permissions(conn, user_id, body.permissions)
    except UniqueViolation as exc:
        raise invalid("login_taken", "Логин, почта или телефон уже заняты") from exc
    if password_changed:
        conn.execute(
            "UPDATE refresh_tokens SET revoked_at = now() WHERE user_id = %s AND revoked_at IS NULL",
            (user_id,),
        )
    audit(conn, user.id, "user.update", "user", user_id)
    return _user_row(conn, user_id)


def block_user(conn, actor, user_id) -> AdminUser:
    actor.require("users.manage")
    if actor.id == user_id:
        raise forbidden("Нельзя заблокировать свою учётную запись")
    must(one(conn, "SELECT 1 FROM users WHERE id = %s", (user_id,)))
    conn.execute("UPDATE users SET status = 'blocked' WHERE id = %s", (user_id,))
    conn.execute(
        "UPDATE refresh_tokens SET revoked_at = now() WHERE user_id = %s AND revoked_at IS NULL",
        (user_id,),
    )
    audit(conn, actor.id, "user.block", "user", user_id)
    return _user_row(conn, user_id)


def unblock_user(conn, actor, user_id) -> AdminUser:
    actor.require("users.manage")
    must(one(conn, "SELECT 1 FROM users WHERE id = %s", (user_id,)))
    conn.execute(
        """
        UPDATE users
        SET status = CASE WHEN password_hash IS NULL THEN 'pending'::account_status ELSE 'active'::account_status END
        WHERE id = %s
        """,
        (user_id,),
    )
    audit(conn, actor.id, "user.unblock", "user", user_id)
    return _user_row(conn, user_id)


def list_permissions(conn, user) -> list[PermissionInfo]:
    user.require("users.manage")
    return [
        PermissionInfo(code=row["code"], description=row["description"])
        for row in many(conn, "SELECT code, description FROM permissions ORDER BY code")
    ]


def replace_permissions(conn, user, user_id, codes: list[str]) -> AdminUser:
    user.require("users.manage")
    must(one(conn, "SELECT 1 FROM users WHERE id = %s", (user_id,)))
    try:
        with conn.transaction():
            _replace_permissions(conn, user_id, codes)
    except UniqueViolation as exc:
        raise invalid("unknown_permission", "Такого права нет") from exc
    audit(conn, user.id, "user.permissions", "user", user_id, {"permissions": codes})
    return _user_row(conn, user_id)


def validate_formula(definition: dict) -> dict:
    kind = definition.get("type")
    source = definition.get("of")
    if kind not in ("weighted_average", "mean", "sum"):
        raise invalid("bad_formula", "Тип формулы: weighted_average, mean или sum")
    if source != "final_numeric_grades":
        raise invalid("bad_formula", "Формула считается по итоговым числовым оценкам")
    if kind == "weighted_average" and definition.get("weight") not in (None, "credits"):
        raise invalid("bad_formula", "Вес взвешенного среднего — кредиты")
    clean = {"type": kind, "of": source}
    if kind == "weighted_average":
        clean["weight"] = "credits"
    return clean


def get_formula(conn, user) -> RatingFormula:
    user.require("settings.manage")
    row = must(one(conn, "SELECT id, name, definition FROM rating_formulas WHERE is_active"), "Формула рейтинга не задана")
    return RatingFormula(id=row["id"], name=row["name"], definition=row["definition"])


def replace_formula(conn, user, body) -> RatingFormula:
    user.require("settings.manage")
    definition = validate_formula(body.definition)
    conn.execute("UPDATE rating_formulas SET is_active = false WHERE is_active")
    row = conn.execute(
        """
        INSERT INTO rating_formulas (name, definition, is_active, updated_by)
        VALUES (%s, %s, true, %s)
        RETURNING id, name, definition
        """,
        (body.name.strip(), Json(definition), user.id),
    ).fetchone()
    for student in many(conn, "SELECT DISTINCT student_user_id FROM grades"):
        recompute_student(conn, student["student_user_id"])
    audit(conn, user.id, "rating_formula.replace", "rating_formula", row["id"])
    return RatingFormula(id=row["id"], name=row["name"], definition=row["definition"])


def save_certificate_type(conn, user, body, type_id=None):
    from app.services.desk import certificate_types

    user.require("settings.manage")
    if not body.delivery_modes:
        raise invalid("modes_required", "Укажите хотя бы один способ выдачи")
    if type_id is None:
        row = conn.execute(
            """
            INSERT INTO certificate_types (code, title, enabled)
            VALUES (%s, %s, %s) RETURNING id
            """,
            (body.code.strip(), body.title.strip(), body.enabled),
        ).fetchone()
        type_id = row["id"]
        audit(conn, user.id, "certificate_type.create", "certificate_type", type_id)
    else:
        must(one(conn, "SELECT 1 FROM certificate_types WHERE id = %s", (type_id,)))
        conn.execute(
            "UPDATE certificate_types SET code = %s, title = %s, enabled = %s WHERE id = %s",
            (body.code.strip(), body.title.strip(), body.enabled, type_id),
        )
        audit(conn, user.id, "certificate_type.update", "certificate_type", type_id)
    conn.execute("DELETE FROM certificate_type_modes WHERE type_id = %s", (type_id,))
    for mode in dict.fromkeys(body.delivery_modes):
        conn.execute(
            "INSERT INTO certificate_type_modes (type_id, mode) VALUES (%s, %s)",
            (type_id, mode),
        )
    for item in certificate_types(conn, user, include_disabled=True):
        if item.id == type_id:
            return item
    raise invalid("type_missing", "Вид справки не сохранился")


def create_contract(conn, user, body) -> Contract:
    user.require("contracts.manage")
    row = conn.execute(
        """
        INSERT INTO contracts (student_user_id, kind, number, title, opened_on)
        VALUES (%s, %s, %s, %s, %s)
        RETURNING id
        """,
        (body.student_id, body.kind, body.number.strip(), body.title, body.opened_on),
    ).fetchone()
    audit(conn, user.id, "contract.create", "contract", row["id"])
    from app.services.desk import get_contract

    return get_contract(conn, user, row["id"])


def create_ledger(conn, user, contract_id, body) -> LedgerEntry:
    user.require("contracts.manage")
    must(one(conn, "SELECT 1 FROM contracts WHERE id = %s", (contract_id,)), "Договор не найден")
    amount = parse_amount(body.amount)
    row = conn.execute(
        """
        INSERT INTO ledger_entries (contract_id, direction, amount, occurred_on, description, reverses_entry_id, created_by)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        RETURNING id, direction, amount, occurred_on, description, reverses_entry_id
        """,
        (contract_id, body.direction, amount, body.occurred_on, body.description, body.reverses_entry_id, user.id),
    ).fetchone()
    reversed_flag = body.reverses_entry_id is not None
    audit(conn, user.id, "ledger.create", "ledger_entry", row["id"])
    return _ledger({**row, "reversed": reversed_flag})


def list_scholarships(conn, user, student_id) -> list[ScholarshipGrant]:
    user.require("scholarships.manage")
    params: tuple = ()
    clause = ""
    if student_id:
        clause = "WHERE student_user_id = %s"
        params = (student_id,)
    return [
        ScholarshipGrant(
            id=row["id"],
            title=row["title"],
            amount=money(row["amount"]),
            next_payout_on=row["next_payout_on"],
            active=row["active"],
            student_id=row["student_user_id"],
        )
        for row in many(conn, f"SELECT * FROM scholarship_grants {clause} ORDER BY created_at DESC", params)
    ]


def create_scholarship(conn, user, body) -> ScholarshipGrant:
    user.require("scholarships.manage")
    amount = parse_amount(body.amount, allow_zero=True)
    row = conn.execute(
        """
        INSERT INTO scholarship_grants (student_user_id, title, amount, next_payout_on)
        VALUES (%s, %s, %s, %s)
        RETURNING *
        """,
        (body.student_id, body.title.strip(), amount, body.next_payout_on),
    ).fetchone()
    audit(conn, user.id, "scholarship.create", "scholarship_grant", row["id"])
    return ScholarshipGrant(
        id=row["id"],
        title=row["title"],
        amount=money(row["amount"]),
        next_payout_on=row["next_payout_on"],
        active=row["active"],
        student_id=row["student_user_id"],
    )


def create_payout(conn, user, grant_id, body) -> ScholarshipPayout:
    user.require("scholarships.manage")
    must(one(conn, "SELECT 1 FROM scholarship_grants WHERE id = %s", (grant_id,)), "Стипендия не найдена")
    amount = parse_amount(body.amount, allow_zero=True)
    row = conn.execute(
        """
        INSERT INTO scholarship_payouts (grant_id, amount, paid_on)
        VALUES (%s, %s, %s)
        RETURNING id, amount, paid_on, grant_id
        """,
        (grant_id, amount, body.paid_on),
    ).fetchone()
    audit(conn, user.id, "scholarship.payout", "scholarship_payout", row["id"])
    return ScholarshipPayout(id=row["id"], amount=money(row["amount"]), paid_on=row["paid_on"], grant_id=row["grant_id"])


def list_admin_corrections(conn, user, status: str | None) -> list[ProfileCorrection]:
    user.require("data.correct")
    params: tuple = ()
    clause = ""
    if status:
        clause = "WHERE c.status = %s"
        params = (status,)
    rows = many(
        conn,
        f"""
        SELECT c.id, c.field_name, c.requested_value, c.comment, c.status, c.created_at,
               c.student_user_id, u.last_name, u.first_name, u.middle_name
        FROM profile_corrections c
        JOIN users u ON u.id = c.student_user_id
        {clause}
        ORDER BY c.created_at DESC
        """,
        params,
    )
    return [
        ProfileCorrection(
            id=row["id"],
            field_name=row["field_name"],
            requested_value=row["requested_value"],
            comment=row["comment"],
            status=row["status"],
            created_at=row["created_at"],
            student_id=row["student_user_id"],
            student_name=person(row),
        )
        for row in rows
    ]


def decide_correction(conn, user, correction_id, decision: str) -> ProfileCorrection:
    user.require("data.correct")
    row = must(
        one(
            conn,
            """
            SELECT c.*, u.last_name, u.first_name, u.middle_name
            FROM profile_corrections c
            JOIN users u ON u.id = c.student_user_id
            WHERE c.id = %s
            """,
            (correction_id,),
        ),
        "Запрос не найден",
    )
    if row["status"] != "pending":
        raise invalid("already_decided", "Этот запрос уже рассмотрен")
    status = "rejected"
    if decision == "apply":
        _apply_correction(conn, row)
        status = "applied"
    conn.execute(
        """
        UPDATE profile_corrections
        SET status = %s, reviewer_user_id = %s, decided_at = now()
        WHERE id = %s
        """,
        (status, user.id, correction_id),
    )
    notify(conn, row["student_user_id"], "correction_updated", "Запрос на исправление сведений рассмотрен")
    audit(conn, user.id, "correction.decide", "profile_correction", correction_id, {"decision": decision})
    fresh = must(
        one(
            conn,
            """
            SELECT c.*, u.last_name, u.first_name, u.middle_name
            FROM profile_corrections c JOIN users u ON u.id = c.student_user_id
            WHERE c.id = %s
            """,
            (correction_id,),
        )
    )
    return ProfileCorrection(
        id=fresh["id"],
        field_name=fresh["field_name"],
        requested_value=fresh["requested_value"],
        comment=fresh["comment"],
        status=fresh["status"],
        created_at=fresh["created_at"],
        student_id=fresh["student_user_id"],
        student_name=person(fresh),
    )


def _apply_correction(conn, row) -> None:
    field = row["field_name"]
    value = row["requested_value"].strip()
    student_id = row["student_user_id"]
    if field == "group":
        must(one(conn, "SELECT 1 FROM groups WHERE id = %s", (value,)), "Такой группы нет")
        conn.execute("UPDATE student_profiles SET group_id = %s WHERE user_id = %s", (value, student_id))
    elif field == "course":
        try:
            course = int(value)
        except ValueError as exc:
            raise invalid("bad_course", "Курс — число от 1 до 6") from exc
        if course < 1 or course > 6:
            raise invalid("bad_course", "Курс — число от 1 до 6")
        conn.execute("UPDATE student_profiles SET course = %s WHERE user_id = %s", (course, student_id))
    elif field == "funding":
        if value not in ("budget", "paid", "targeted"):
            raise invalid("bad_funding", "Форма обучения: budget, paid или targeted")
        conn.execute("UPDATE student_profiles SET funding = %s WHERE user_id = %s", (value, student_id))
    elif field == "lives_in_dorm":
        normalized = value.lower().replace("ё", "е")
        if normalized in ("true", "1", "да", "yes"):
            flag = True
        elif normalized in ("false", "0", "нет", "no"):
            flag = False
        else:
            raise invalid("bad_flag", "Для общежития укажите да или нет")
        conn.execute("UPDATE student_profiles SET lives_in_dorm = %s WHERE user_id = %s", (flag, student_id))
    elif field in ("record_book_number", "student_card_number"):
        try:
            with conn.transaction():
                conn.execute(
                    f"UPDATE student_profiles SET {field} = %s WHERE user_id = %s",
                    (value, student_id),
                )
        except UniqueViolation as exc:
            raise invalid("number_taken", "Такой номер уже записан у другого студента") from exc
    else:
        raise invalid("unknown_field", "Это поле не исправляется")


def list_audit(conn, user, cursor: str | None, limit: int | None, entity_type: str | None) -> AuditPage:
    user.require("audit.read")
    size = clamp_limit(limit)
    filters = ["TRUE"]
    params: list = []
    if entity_type:
        filters.append("entity_type = %s")
        params.append(entity_type)
    if cursor:
        try:
            last_id = int(cursor)
        except ValueError as exc:
            raise invalid("bad_cursor", "Некорректная страница списка") from exc
        filters.append("id < %s")
        params.append(last_id)
    params.append(size + 1)
    rows = many(
        conn,
        f"""
        SELECT id, actor_user_id, action, entity_type, entity_id, payload, created_at
        FROM audit_events
        WHERE {' AND '.join(filters)}
        ORDER BY id DESC
        LIMIT %s
        """,
        tuple(params),
    )
    next_cursor = None
    if len(rows) > size:
        rows = rows[:size]
        next_cursor = str(rows[-1]["id"])
    return AuditPage(
        items=[
            AuditEvent(
                id=row["id"],
                actor_user_id=row["actor_user_id"],
                action=row["action"],
                entity_type=row["entity_type"],
                entity_id=row["entity_id"],
                payload=row["payload"] or {},
                created_at=row["created_at"],
            )
            for row in rows
        ],
        next_cursor=next_cursor,
    )
