from app.errors import forbidden, invalid
from app.schemas import (
    EmployeeProfile,
    Me,
    Rating,
    ScholarshipGrant,
    ScholarshipPayout,
    ScholarshipView,
    StudentCard,
    StudentProfile,
)
from app.services.common import (
    blank,
    enabled_sections,
    load_university,
    many,
    must,
    one,
    require_section,
)
from app.util import decimal_str, full_name, money

from psycopg.errors import UniqueViolation


def build_me(conn, user) -> Me:
    student = None
    employee = None
    if user.role == "student":
        row = one(
            conn,
            """
            SELECT sp.group_id, g.name AS group_name, ou.name AS org_unit_name,
                   sp.course, sp.funding, sp.record_book_number, sp.student_card_number,
                   sp.lives_in_dorm
            FROM student_profiles sp
            LEFT JOIN groups g ON g.id = sp.group_id
            LEFT JOIN org_units ou ON ou.id = g.org_unit_id
            WHERE sp.user_id = %s
            """,
            (user.id,),
        )
        if row:
            student = StudentProfile(
                group_id=row["group_id"],
                group_name=row["group_name"],
                org_unit_name=row["org_unit_name"],
                course=row["course"],
                funding=row["funding"],
                record_book_number=row["record_book_number"],
                student_card_number=row["student_card_number"],
                lives_in_dorm=row["lives_in_dorm"],
            )
    elif user.role == "employee":
        row = one(
            conn,
            """
            SELECT ep.position, ou.name AS org_unit_name
            FROM employee_profiles ep
            LEFT JOIN org_units ou ON ou.id = ep.org_unit_id
            WHERE ep.user_id = %s
            """,
            (user.id,),
        )
        if row:
            employee = EmployeeProfile(org_unit_name=row["org_unit_name"], position=row["position"])
    return Me(
        id=user.id,
        role=user.role,
        status=user.status,
        last_name=user.last_name,
        first_name=user.first_name,
        middle_name=user.middle_name,
        login=user.login,
        email=user.email,
        phone=user.phone,
        permissions=sorted(user.permissions),
        enabled_sections=enabled_sections(conn),
        student=student,
        employee=employee,
    )


def update_contacts(conn, user, body) -> Me:
    sent = body.model_fields_set
    email = blank(body.email) if "email" in sent else user.email
    phone = blank(body.phone) if "phone" in sent else user.phone
    try:
        with conn.transaction():
            conn.execute(
                "UPDATE users SET email = %s, phone = %s WHERE id = %s",
                (email, phone, user.id),
            )
    except UniqueViolation as exc:
        raise invalid("contact_taken", "Этот адрес или телефон уже используется") from exc
    fresh = user.__class__(
        id=user.id,
        role=user.role,
        status=user.status,
        last_name=user.last_name,
        first_name=user.first_name,
        middle_name=user.middle_name,
        login=user.login,
        email=email,
        phone=phone,
        permissions=user.permissions,
    )
    return build_me(conn, fresh)


def student_card(conn, user) -> StudentCard:
    if user.role != "student":
        raise forbidden("Карточка есть у студента")
    row = must(
        one(
            conn,
            """
            SELECT sp.student_card_number, sp.record_book_number, sp.photo_file_id,
                   g.name AS group_name
            FROM student_profiles sp
            LEFT JOIN groups g ON g.id = sp.group_id
            WHERE sp.user_id = %s
            """,
            (user.id,),
        ),
        "Профиль студента не найден",
    )
    university = load_university(conn)
    card = row["student_card_number"] or ""
    photo = f"/api/v1/files/{row['photo_file_id']}" if row["photo_file_id"] else None
    return StudentCard(
        full_name=full_name(user.last_name, user.first_name, user.middle_name),
        student_card_number=row["student_card_number"],
        record_book_number=row["record_book_number"],
        group_name=row["group_name"],
        photo_url=photo,
        qr_payload=f"lkbonch:{university['short_name']}:{card}",
    )


def my_scholarship(conn, user) -> ScholarshipView:
    if user.role != "student":
        raise forbidden()
    require_section(conn, "scholarships")
    grants = [
        ScholarshipGrant(
            id=row["id"],
            title=row["title"],
            amount=money(row["amount"]),
            next_payout_on=row["next_payout_on"],
            active=row["active"],
            student_id=user.id,
        )
        for row in many(
            conn,
            """
            SELECT id, title, amount, next_payout_on, active
            FROM scholarship_grants
            WHERE student_user_id = %s
            ORDER BY created_at DESC
            """,
            (user.id,),
        )
    ]
    payouts = [
        ScholarshipPayout(
            id=row["id"],
            amount=money(row["amount"]),
            paid_on=row["paid_on"],
            grant_id=row["grant_id"],
        )
        for row in many(
            conn,
            """
            SELECT p.id, p.amount, p.paid_on, p.grant_id
            FROM scholarship_payouts p
            JOIN scholarship_grants g ON g.id = p.grant_id
            WHERE g.student_user_id = %s
            ORDER BY p.paid_on DESC
            """,
            (user.id,),
        )
    ]
    return ScholarshipView(grants=grants, payouts=payouts)


def my_rating(conn, user) -> Rating:
    if user.role != "student":
        raise forbidden()
    row = one(
        conn,
        "SELECT score, computed_at FROM rating_snapshots WHERE student_user_id = %s",
        (user.id,),
    )
    if row is None:
        return Rating(score=None, computed_at=None)
    return Rating(score=decimal_str(row["score"], "0.001"), computed_at=row["computed_at"])
