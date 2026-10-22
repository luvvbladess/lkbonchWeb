from app.errors import forbidden, invalid
from app.schemas import (
    Diary,
    DiarySemester,
    ElectiveApplication,
    ElectiveOffer,
    Grade,
    JournalStudent,
    ProfileCorrection,
    TeachingAssignment,
)
from app.services.common import (
    many,
    must,
    notify,
    one,
    parse_score,
    person,
    require_section,
    university_today,
)
from app.services.rating import recompute_student
from app.util import decimal_str


def grade_model(row) -> Grade:
    return Grade(
        id=row["id"],
        discipline_name=row["discipline_name"],
        semester_id=row["semester_id"],
        semester_title=row.get("semester_title") or "",
        student_id=row.get("student_user_id"),
        student_name=row.get("student_name"),
        kind=row["kind"],
        title=row["title"] or "",
        score=None if row["score"] is None else decimal_str(row["score"]),
        label=row["label"] or "",
        is_final=row["is_final"],
        is_debt=row["is_debt"],
        credits=decimal_str(row["credits"], "0.1"),
    )


_GRADE_SELECT = """
    SELECT g.id, g.student_user_id, g.discipline_id, g.semester_id, g.kind, g.title,
           g.score, g.label, g.is_final, g.is_debt, g.credits,
           d.name AS discipline_name, s.title AS semester_title,
           concat_ws(' ', u.last_name, u.first_name, NULLIF(u.middle_name, '')) AS student_name
    FROM grades g
    JOIN disciplines d ON d.id = g.discipline_id
    JOIN semesters s ON s.id = g.semester_id
    JOIN users u ON u.id = g.student_user_id
"""


def diary(conn, user, semester_id) -> Diary:
    if user.role != "student":
        raise forbidden()
    require_section(conn, "diary")
    params: list = [user.id]
    clause = ""
    if semester_id is not None:
        clause = "AND g.semester_id = %s"
        params.append(semester_id)
    rows = many(
        conn,
        f"""
        {_GRADE_SELECT}
        WHERE g.student_user_id = %s {clause}
        ORDER BY s.starts_on DESC, d.name, g.created_at
        """,
        tuple(params),
    )
    grouped: dict = {}
    order: list = []
    for row in rows:
        key = row["semester_id"]
        if key not in grouped:
            grouped[key] = DiarySemester(semester_id=key, title=row["semester_title"], grades=[])
            order.append(key)
        grouped[key].grades.append(grade_model(row))
    return Diary(semesters=[grouped[key] for key in order])


def debts(conn, user) -> list[Grade]:
    if user.role != "student":
        raise forbidden()
    require_section(conn, "diary")
    rows = many(
        conn,
        f"""
        {_GRADE_SELECT}
        WHERE g.student_user_id = %s AND g.is_debt
        ORDER BY s.starts_on DESC, d.name
        """,
        (user.id,),
    )
    return [grade_model(row) for row in rows]


def teaching(conn, user) -> list[TeachingAssignment]:
    if user.role != "employee":
        raise forbidden()
    require_section(conn, "diary")
    rows = many(
        conn,
        """
        SELECT gd.id, gd.discipline_id, gd.semester_id, d.name AS discipline_name,
               g.name AS group_name, s.title AS semester_title, gd.kind
        FROM group_disciplines gd
        JOIN disciplines d ON d.id = gd.discipline_id
        JOIN groups g ON g.id = gd.group_id
        JOIN semesters s ON s.id = gd.semester_id
        WHERE gd.teacher_user_id = %s
        ORDER BY s.starts_on DESC, g.name, d.name
        """,
        (user.id,),
    )
    return [
        TeachingAssignment(
            group_discipline_id=row["id"],
            discipline_id=row["discipline_id"],
            semester_id=row["semester_id"],
            discipline_name=row["discipline_name"],
            group_name=row["group_name"],
            semester_title=row["semester_title"],
            kind=row["kind"],
        )
        for row in rows
    ]


def _assignment_for_teacher(conn, user_id, group_discipline_id):
    return must(
        one(
            conn,
            """
            SELECT gd.id, gd.group_id, gd.discipline_id, gd.semester_id, gd.credits
            FROM group_disciplines gd
            WHERE gd.id = %s AND gd.teacher_user_id = %s
            """,
            (group_discipline_id, user_id),
        ),
        "Назначение не найдено",
    )


def teaching_grades(conn, user, group_discipline_id) -> list[JournalStudent]:
    if user.role != "employee":
        raise forbidden()
    item = _assignment_for_teacher(conn, user.id, group_discipline_id)
    students = many(
        conn,
        """
        SELECT u.id, u.last_name, u.first_name, u.middle_name
        FROM student_profiles sp
        JOIN users u ON u.id = sp.user_id
        WHERE sp.group_id = %s
        ORDER BY u.last_name, u.first_name
        """,
        (item["group_id"],),
    )
    grade_rows = many(
        conn,
        f"""
        {_GRADE_SELECT}
        WHERE g.discipline_id = %s AND g.semester_id = %s
          AND g.student_user_id IN (
              SELECT user_id FROM student_profiles WHERE group_id = %s
          )
        ORDER BY g.created_at
        """,
        (item["discipline_id"], item["semester_id"], item["group_id"]),
    )
    by_student: dict = {}
    for row in grade_rows:
        by_student.setdefault(row["student_user_id"], []).append(grade_model(row))
    return [
        JournalStudent(student_id=row["id"], student_name=person(row), grades=by_student.get(row["id"], []))
        for row in students
    ]


def _teacher_link(conn, teacher_id, student_id, discipline_id, semester_id):
    link = one(
        conn,
        """
        SELECT gd.credits
        FROM group_disciplines gd
        JOIN student_profiles sp ON sp.group_id = gd.group_id AND sp.user_id = %s
        WHERE gd.teacher_user_id = %s
          AND gd.discipline_id = %s
          AND gd.semester_id = %s
        """,
        (student_id, teacher_id, discipline_id, semester_id),
    )
    if link is None:
        raise forbidden("Оценку ставит преподаватель этой дисциплины в группе студента")
    return link


def create_grade(conn, user, body) -> Grade:
    if user.role != "employee":
        raise forbidden()
    link = _teacher_link(conn, user.id, body.student_id, body.discipline_id, body.semester_id)
    row = conn.execute(
        """
        INSERT INTO grades (
            student_user_id, discipline_id, semester_id, kind, title, score, label,
            is_final, credits, recorded_by
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id
        """,
        (
            body.student_id,
            body.discipline_id,
            body.semester_id,
            body.kind,
            body.title,
            parse_score(body.score),
            body.label,
            body.is_final,
            link["credits"],
            user.id,
        ),
    ).fetchone()
    recompute_student(conn, body.student_id)
    notify(conn, body.student_id, "grade_posted", "Новая оценка", body.title, {"gradeId": str(row["id"])})
    saved = must(one(conn, f"{_GRADE_SELECT} WHERE g.id = %s", (row["id"],)))
    return grade_model(saved)


def update_grade(conn, user, grade_id, body) -> Grade:
    if user.role != "employee":
        raise forbidden()
    current = must(one(conn, "SELECT * FROM grades WHERE id = %s", (grade_id,)), "Оценка не найдена")
    if (
        current["student_user_id"] != body.student_id
        or current["discipline_id"] != body.discipline_id
        or current["semester_id"] != body.semester_id
    ):
        raise invalid("grade_identity", "Студента, дисциплину и семестр оценки не меняют")
    link = _teacher_link(conn, user.id, body.student_id, body.discipline_id, body.semester_id)
    conn.execute(
        """
        UPDATE grades
        SET kind = %s, title = %s, score = %s, label = %s, is_final = %s, credits = %s, recorded_by = %s
        WHERE id = %s
        """,
        (
            body.kind,
            body.title,
            parse_score(body.score),
            body.label,
            body.is_final,
            link["credits"],
            user.id,
            grade_id,
        ),
    )
    recompute_student(conn, body.student_id)
    saved = must(one(conn, f"{_GRADE_SELECT} WHERE g.id = %s", (grade_id,)))
    return grade_model(saved)


def _elective_window(semester, today) -> bool:
    if semester["status"] == "closed":
        return False
    start = semester["elective_open_on"] or semester["starts_on"]
    end = semester["elective_change_until"] or semester["elective_close_on"] or semester["ends_on"]
    return start <= today <= end


def list_electives(conn, user) -> list[ElectiveOffer]:
    if user.role != "student":
        raise forbidden()
    require_section(conn, "electives")
    rows = many(
        conn,
        """
        SELECT gd.id AS group_discipline_id, d.name AS discipline_name, gd.credits,
               b.title AS block_title,
               ea.id AS application_id, ea.status, ea.submitted_at
        FROM group_disciplines gd
        JOIN elective_blocks b ON b.id = gd.elective_block_id
        JOIN disciplines d ON d.id = gd.discipline_id
        JOIN semesters s ON s.id = gd.semester_id
        JOIN student_profiles sp ON sp.group_id = gd.group_id
        LEFT JOIN elective_applications ea
          ON ea.group_discipline_id = gd.id
         AND ea.student_user_id = sp.user_id
         AND ea.status IN ('pending', 'approved')
        WHERE sp.user_id = %s AND gd.kind = 'elective' AND s.status = 'active'
        ORDER BY b.title, d.name
        """,
        (user.id,),
    )
    offers = []
    for row in rows:
        application = None
        if row["application_id"]:
            application = ElectiveApplication(
                id=row["application_id"],
                status=row["status"],
                discipline_name=row["discipline_name"],
                submitted_at=row["submitted_at"],
            )
        offers.append(
            ElectiveOffer(
                group_discipline_id=row["group_discipline_id"],
                discipline_name=row["discipline_name"],
                credits=decimal_str(row["credits"], "0.1"),
                block_title=row["block_title"],
                application=application,
            )
        )
    return offers


def apply_elective(conn, user, group_discipline_id) -> ElectiveApplication:
    if user.role != "student":
        raise forbidden()
    require_section(conn, "electives")
    item = must(
        one(
            conn,
            """
            SELECT gd.id, gd.elective_block_id, gd.discipline_id, s.status, s.starts_on, s.ends_on,
                   s.elective_open_on, s.elective_close_on, s.elective_change_until,
                   d.name AS discipline_name
            FROM group_disciplines gd
            JOIN semesters s ON s.id = gd.semester_id
            JOIN disciplines d ON d.id = gd.discipline_id
            JOIN student_profiles sp ON sp.group_id = gd.group_id AND sp.user_id = %s
            WHERE gd.id = %s AND gd.kind = 'elective'
            """,
            (user.id, group_discipline_id),
        ),
        "Выборная дисциплина не найдена",
    )
    if not _elective_window(item, university_today(conn)):
        raise invalid("elective_closed", "Срок выбора дисциплины уже прошёл")
    conn.execute(
        "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
        (f"{user.id}:{item['elective_block_id']}",),
    )
    conn.execute(
        """
        UPDATE elective_applications
        SET status = 'withdrawn', decided_at = now(), decided_by = %s
        WHERE student_user_id = %s
          AND elective_block_id = %s
          AND status IN ('pending', 'approved')
          AND group_discipline_id <> %s
        """,
        (user.id, user.id, item["elective_block_id"], group_discipline_id),
    )
    existing = one(
        conn,
        """
        SELECT id, status, submitted_at
        FROM elective_applications
        WHERE student_user_id = %s AND group_discipline_id = %s
          AND status IN ('pending', 'approved')
        """,
        (user.id, group_discipline_id),
    )
    if existing is None:
        existing = conn.execute(
            """
            INSERT INTO elective_applications (student_user_id, group_discipline_id, elective_block_id)
            VALUES (%s, %s, %s)
            RETURNING id, status, submitted_at
            """,
            (user.id, group_discipline_id, item["elective_block_id"]),
        ).fetchone()
    return ElectiveApplication(
        id=existing["id"],
        status=existing["status"],
        discipline_name=item["discipline_name"],
        student_name=person_name(user),
        submitted_at=existing["submitted_at"],
    )


def person_name(user) -> str:
    return f"{user.last_name} {user.first_name}".strip()


def withdraw_elective(conn, user, application_id) -> ElectiveApplication:
    if user.role != "student":
        raise forbidden()
    row = must(
        one(
            conn,
            """
            SELECT ea.id, ea.status, ea.submitted_at, ea.student_user_id,
                   s.status AS semester_status, s.starts_on, s.ends_on,
                   s.elective_open_on, s.elective_close_on, s.elective_change_until,
                   d.name AS discipline_name
            FROM elective_applications ea
            JOIN group_disciplines gd ON gd.id = ea.group_discipline_id
            JOIN semesters s ON s.id = gd.semester_id
            JOIN disciplines d ON d.id = gd.discipline_id
            WHERE ea.id = %s
            """,
            (application_id,),
        ),
        "Заявка не найдена",
    )
    if row["student_user_id"] != user.id:
        raise forbidden()
    if row["status"] not in ("pending", "approved"):
        raise invalid("elective_closed", "Эту заявку уже нельзя отозвать")
    window = {
        "status": row["semester_status"],
        "starts_on": row["starts_on"],
        "ends_on": row["ends_on"],
        "elective_open_on": row["elective_open_on"],
        "elective_close_on": row["elective_close_on"],
        "elective_change_until": row["elective_change_until"],
    }
    if not _elective_window(window, university_today(conn)):
        raise invalid("elective_closed", "Срок изменения выбора уже прошёл")
    conn.execute(
        """
        UPDATE elective_applications
        SET status = 'withdrawn', decided_at = now(), decided_by = %s
        WHERE id = %s
        """,
        (user.id, application_id),
    )
    return ElectiveApplication(
        id=row["id"],
        status="withdrawn",
        discipline_name=row["discipline_name"],
        submitted_at=row["submitted_at"],
    )


def elective_queue(conn, user, status: str | None) -> list[ElectiveApplication]:
    user.require("electives.review")
    params: list = []
    clause = ""
    if status:
        clause = "WHERE ea.status = %s"
        params.append(status)
    rows = many(
        conn,
        f"""
        SELECT ea.id, ea.status, ea.submitted_at, d.name AS discipline_name,
               u.last_name, u.first_name, u.middle_name
        FROM elective_applications ea
        JOIN group_disciplines gd ON gd.id = ea.group_discipline_id
        JOIN disciplines d ON d.id = gd.discipline_id
        JOIN users u ON u.id = ea.student_user_id
        {clause}
        ORDER BY ea.submitted_at
        """,
        tuple(params),
    )
    return [
        ElectiveApplication(
            id=row["id"],
            status=row["status"],
            discipline_name=row["discipline_name"],
            student_name=person(row),
            submitted_at=row["submitted_at"],
        )
        for row in rows
    ]


def decide_elective(conn, user, application_id, decision: str) -> ElectiveApplication:
    user.require("electives.review")
    row = must(
        one(
            conn,
            """
            SELECT ea.id, ea.status, ea.student_user_id, ea.submitted_at, d.name AS discipline_name,
                   u.last_name, u.first_name, u.middle_name
            FROM elective_applications ea
            JOIN group_disciplines gd ON gd.id = ea.group_discipline_id
            JOIN disciplines d ON d.id = gd.discipline_id
            JOIN users u ON u.id = ea.student_user_id
            WHERE ea.id = %s
            """,
            (application_id,),
        ),
        "Заявка не найдена",
    )
    if row["status"] != "pending":
        raise invalid("already_decided", "По этой заявке решение уже есть")
    conn.execute(
        """
        UPDATE elective_applications
        SET status = %s, decided_at = now(), decided_by = %s
        WHERE id = %s
        """,
        (decision, user.id, application_id),
    )
    notify(
        conn,
        row["student_user_id"],
        "elective_updated",
        "Заявка на выборную дисциплину рассмотрена",
        row["discipline_name"],
        {"applicationId": str(application_id)},
    )
    return ElectiveApplication(
        id=row["id"],
        status=decision,
        discipline_name=row["discipline_name"],
        student_name=person(row),
        submitted_at=row["submitted_at"],
    )


def list_corrections(conn, user) -> list[ProfileCorrection]:
    if user.role != "student":
        raise forbidden()
    rows = many(
        conn,
        """
        SELECT id, field_name, requested_value, comment, status, created_at, student_user_id
        FROM profile_corrections
        WHERE student_user_id = %s
        ORDER BY created_at DESC
        """,
        (user.id,),
    )
    name = person_name(user)
    return [
        ProfileCorrection(
            id=row["id"],
            field_name=row["field_name"],
            requested_value=row["requested_value"],
            comment=row["comment"],
            status=row["status"],
            created_at=row["created_at"],
            student_id=row["student_user_id"],
            student_name=name,
        )
        for row in rows
    ]


def create_correction(conn, user, body) -> ProfileCorrection:
    if user.role != "student":
        raise forbidden()
    if not body.requested_value.strip():
        raise invalid("empty_value", "Укажите новое значение")
    row = conn.execute(
        """
        INSERT INTO profile_corrections (student_user_id, field_name, requested_value, comment)
        VALUES (%s, %s, %s, %s)
        RETURNING id, created_at
        """,
        (user.id, body.field_name, body.requested_value.strip(), body.comment),
    ).fetchone()
    return ProfileCorrection(
        id=row["id"],
        field_name=body.field_name,
        requested_value=body.requested_value.strip(),
        comment=body.comment,
        status="pending",
        created_at=row["created_at"],
        student_id=user.id,
        student_name=person_name(user),
    )
