from datetime import UTC, datetime

from app.errors import forbidden, invalid
from app.schemas import Attendance, Lesson, LessonDetail, LessonPerson
from app.services.common import many, must, notify_many, one, person, require_section
from app.util import full_name


def _lesson_sql(where: str) -> str:
    return f"""
        SELECT l.id, l.starts_at, l.ends_at, l.room, l.note, l.publication_status,
               l.cancelled_at, l.teacher_user_id, l.semester_id, l.discipline_id,
               d.name AS discipline_name,
               t.last_name AS teacher_last_name,
               t.first_name AS teacher_first_name,
               t.middle_name AS teacher_middle_name,
               COALESCE(array_agg(g.name ORDER BY g.name) FILTER (WHERE g.id IS NOT NULL), ARRAY[]::text[]) AS group_names
        FROM lessons l
        JOIN disciplines d ON d.id = l.discipline_id
        LEFT JOIN users t ON t.id = l.teacher_user_id
        LEFT JOIN lesson_groups lg ON lg.lesson_id = l.id
        LEFT JOIN groups g ON g.id = lg.group_id
        WHERE {where}
        GROUP BY l.id, d.name, t.last_name, t.first_name, t.middle_name
        ORDER BY l.starts_at
    """


def lesson_model(row) -> Lesson:
    teacher = None
    if row["teacher_last_name"]:
        teacher = full_name(row["teacher_last_name"], row["teacher_first_name"], row["teacher_middle_name"])
    return Lesson(
        id=row["id"],
        discipline_name=row["discipline_name"],
        starts_at=row["starts_at"],
        ends_at=row["ends_at"],
        room=row["room"],
        publication_status=row["publication_status"],
        cancelled=row["cancelled_at"] is not None,
        groups=list(row["group_names"]),
        teacher_name=teacher,
        note=row["note"] or "",
    )


def list_schedule(conn, user, interval_from: datetime, interval_to: datetime) -> list[Lesson]:
    require_section(conn, "schedule")
    if interval_from >= interval_to:
        raise invalid("bad_interval", "Интервал расписания пустой")
    params: list = [interval_to, interval_from]
    if user.role == "student":
        where = """
            l.publication_status = 'published'
            AND l.starts_at < %s AND l.ends_at > %s
            AND EXISTS (
                SELECT 1
                FROM lesson_groups lg2
                JOIN student_profiles sp ON sp.group_id = lg2.group_id
                WHERE lg2.lesson_id = l.id AND sp.user_id = %s
            )
        """
        params.append(user.id)
    elif user.role == "employee":
        where = """
            l.publication_status = 'published'
            AND l.teacher_user_id = %s
            AND l.starts_at < %s AND l.ends_at > %s
        """
        params = [user.id, interval_to, interval_from]
    else:
        where = """
            l.publication_status = 'published'
            AND l.starts_at < %s AND l.ends_at > %s
        """
    return [lesson_model(row) for row in many(conn, _lesson_sql(where), tuple(params))]


def fetch_lesson(conn, lesson_id):
    return one(conn, _lesson_sql("l.id = %s"), (lesson_id,))


def ensure_teacher_presence(conn, lesson_id) -> None:
    conn.execute(
        """
        INSERT INTO attendance_marks (lesson_id, user_id, mark, origin)
        SELECT l.id, l.teacher_user_id, 'present', 'system'
        FROM lessons l
        WHERE l.id = %s
          AND l.publication_status = 'published'
          AND l.cancelled_at IS NULL
          AND l.teacher_user_id IS NOT NULL
          AND l.starts_at <= now()
        ON CONFLICT (lesson_id, user_id) DO NOTHING
        """,
        (lesson_id,),
    )


def _visible(conn, user, lesson_id):
    row = fetch_lesson(conn, lesson_id)
    if row is None:
        return None
    if user.role == "admin":
        return row
    if user.role == "employee" and row["teacher_user_id"] == user.id:
        return row
    if user.role == "student" and row["publication_status"] == "published":
        member = one(
            conn,
            """
            SELECT 1
            FROM lesson_groups lg
            JOIN student_profiles sp ON sp.group_id = lg.group_id
            WHERE lg.lesson_id = %s AND sp.user_id = %s
            """,
            (lesson_id, user.id),
        )
        if member:
            return row
    return None


def _marks(conn, lesson_id, only_user=None) -> list[Attendance]:
    clause = ""
    params: list = [lesson_id]
    if only_user is not None:
        clause = "AND a.user_id = %s"
        params.append(only_user)
    rows = many(
        conn,
        f"""
        SELECT a.user_id, a.mark, a.origin, a.updated_at,
               u.last_name, u.first_name, u.middle_name
        FROM attendance_marks a
        JOIN users u ON u.id = a.user_id
        WHERE a.lesson_id = %s {clause}
        ORDER BY u.last_name, u.first_name
        """,
        tuple(params),
    )
    return [
        Attendance(
            user_id=row["user_id"],
            full_name=person(row),
            mark=row["mark"],
            origin=row["origin"],
            updated_at=row["updated_at"],
        )
        for row in rows
    ]


def _participants(conn, lesson) -> list[LessonPerson]:
    people = []
    if lesson["teacher_user_id"]:
        teacher = one(
            conn,
            "SELECT id, last_name, first_name, middle_name FROM users WHERE id = %s",
            (lesson["teacher_user_id"],),
        )
        if teacher:
            people.append(
                LessonPerson(user_id=teacher["id"], full_name=person(teacher), role="teacher")
            )
    students = many(
        conn,
        """
        SELECT DISTINCT u.id, u.last_name, u.first_name, u.middle_name
        FROM lesson_groups lg
        JOIN student_profiles sp ON sp.group_id = lg.group_id
        JOIN users u ON u.id = sp.user_id
        WHERE lg.lesson_id = %s
        ORDER BY u.last_name, u.first_name
        """,
        (lesson["id"],),
    )
    people.extend(LessonPerson(user_id=row["id"], full_name=person(row), role="student") for row in students)
    return people


def get_lesson(conn, user, lesson_id) -> LessonDetail:
    require_section(conn, "schedule")
    ensure_teacher_presence(conn, lesson_id)
    row = _visible(conn, user, lesson_id)
    row = must(row, "Пара не найдена")
    now = datetime.now(UTC)
    own = _marks(conn, lesson_id, user.id)
    own_mark = own[0] if own else None
    can_mark = (
        user.role == "student"
        and row["publication_status"] == "published"
        and row["cancelled_at"] is None
        and row["starts_at"] <= now <= row["ends_at"]
        and (own_mark is None or own_mark.origin in ("student", "system"))
    )
    if user.role == "student":
        attendance = own
        participants = [item for item in _participants(conn, row) if item.role == "teacher" or item.user_id == user.id]
    else:
        attendance = _marks(conn, lesson_id)
        participants = _participants(conn, row)
    base = lesson_model(row)
    return LessonDetail(
        **base.model_dump(),
        attendance=attendance,
        participants=participants,
        can_mark_self=can_mark,
    )


def mark_own(conn, user, lesson_id) -> Attendance:
    require_section(conn, "schedule")
    if user.role != "student":
        raise forbidden("Отметиться может студент")
    row = must(_visible(conn, user, lesson_id), "Пара не найдена")
    now = datetime.now(UTC)
    if row["publication_status"] != "published" or row["cancelled_at"] is not None or not (row["starts_at"] <= now <= row["ends_at"]):
        raise invalid("attendance_closed", "Не удалось отметиться. Занятие уже закончилось — обратитесь к преподавателю.")
    existing = one(
        conn,
        """
        SELECT mark, origin FROM attendance_marks
        WHERE lesson_id = %s AND user_id = %s
        """,
        (lesson_id, user.id),
    )
    if existing and existing["origin"] in ("teacher", "admin"):
        raise invalid("attendance_locked", "Эту отметку уже поставил преподаватель")
    conn.execute(
        """
        INSERT INTO attendance_marks (lesson_id, user_id, mark, origin, updated_by)
        VALUES (%s, %s, 'present', 'student', %s)
        ON CONFLICT (lesson_id, user_id) DO UPDATE
        SET mark = 'present', origin = 'student', updated_by = EXCLUDED.updated_by, updated_at = now()
        """,
        (lesson_id, user.id, user.id),
    )
    return _marks(conn, lesson_id, user.id)[0]


def correct_student(conn, user, lesson_id, student_id, mark: str) -> Attendance:
    require_section(conn, "schedule")
    row = must(fetch_lesson(conn, lesson_id), "Пара не найдена")
    if row["teacher_user_id"] != user.id:
        raise forbidden("Отметку студента меняет ведущий этой пары")
    if student_id == row["teacher_user_id"]:
        raise forbidden("Явку преподавателя меняет администратор")
    student = one(
        conn,
        """
        SELECT 1
        FROM lesson_groups lg
        JOIN student_profiles sp ON sp.group_id = lg.group_id
        WHERE lg.lesson_id = %s AND sp.user_id = %s
        """,
        (lesson_id, student_id),
    )
    if student is None:
        raise invalid("not_in_lesson", "Этого студента нет на паре")
    conn.execute(
        """
        INSERT INTO attendance_marks (lesson_id, user_id, mark, origin, updated_by)
        VALUES (%s, %s, %s, 'teacher', %s)
        ON CONFLICT (lesson_id, user_id) DO UPDATE
        SET mark = EXCLUDED.mark, origin = 'teacher', updated_by = EXCLUDED.updated_by, updated_at = now()
        """,
        (lesson_id, student_id, mark, user.id),
    )
    return _marks(conn, lesson_id, student_id)[0]


def correct_teacher(conn, user, lesson_id, teacher_id, mark: str) -> Attendance:
    user.require("attendance.correct_teacher")
    row = must(fetch_lesson(conn, lesson_id), "Пара не найдена")
    if row["teacher_user_id"] != teacher_id:
        raise invalid("not_teacher", "Это не ведущий этой пары")
    conn.execute(
        """
        INSERT INTO attendance_marks (lesson_id, user_id, mark, origin, updated_by)
        VALUES (%s, %s, %s, 'admin', %s)
        ON CONFLICT (lesson_id, user_id) DO UPDATE
        SET mark = EXCLUDED.mark, origin = 'admin', updated_by = EXCLUDED.updated_by, updated_at = now()
        """,
        (lesson_id, teacher_id, mark, user.id),
    )
    return _marks(conn, lesson_id, teacher_id)[0]


def replace_lesson_groups(conn, lesson_id, group_ids) -> None:
    if not group_ids:
        raise invalid("groups_required", "У пары должна быть хотя бы одна группа")
    conn.execute("DELETE FROM lesson_groups WHERE lesson_id = %s", (lesson_id,))
    for group_id in dict.fromkeys(group_ids):
        conn.execute(
            "INSERT INTO lesson_groups (lesson_id, group_id) VALUES (%s, %s)",
            (lesson_id, group_id),
        )


def lesson_student_ids(conn, lesson_id) -> list:
    return [
        row["user_id"]
        for row in many(
            conn,
            """
            SELECT DISTINCT sp.user_id
            FROM lesson_groups lg
            JOIN student_profiles sp ON sp.group_id = lg.group_id
            WHERE lg.lesson_id = %s
            """,
            (lesson_id,),
        )
    ]


def notify_schedule(conn, lesson_id, title: str) -> None:
    notify_many(conn, lesson_student_ids(conn, lesson_id), "schedule_changed", title, payload={"lessonId": str(lesson_id)})
