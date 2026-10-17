from pathlib import Path
from uuid import UUID, uuid4

from fastapi import UploadFile
from fastapi.responses import FileResponse

from app.config import settings
from app.errors import ApiError, forbidden, invalid, not_found
from app.schemas import (
    DEMO_MESSAGE,
    CertificateRequest,
    CertificateType,
    Contract,
    DemoPayment,
    DormApplication,
    LedgerEntry,
    Notification,
    NotificationPage,
    PortfolioDocument,
    StoredFile,
)
from app.services.common import (
    clamp_limit,
    load_university,
    many,
    must,
    notify,
    one,
    parse_amount,
    person,
    require_section,
    require_section_for_student,
)
from app.util import decode_cursor, encode_cursor, money


def _file_path(object_key: str) -> Path:
    if not object_key or "/" in object_key or "\\" in object_key or ".." in object_key:
        raise not_found("Файл не найден")
    return Path(settings.file_dir) / object_key


def store_upload(conn, user_id, upload: UploadFile) -> StoredFile:
    data = upload.file.read()
    if len(data) > settings.max_upload_bytes:
        raise ApiError(413, "file_too_large", "Файл больше 20 МБ")
    name = Path(upload.filename or "file").name or "file"
    content_type = upload.content_type or "application/octet-stream"
    file_id = uuid4()
    path = _file_path(str(file_id))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    conn.execute(
        """
        INSERT INTO files (id, object_key, original_name, content_type, size_bytes, uploaded_by)
        VALUES (%s, %s, %s, %s, %s, %s)
        """,
        (file_id, str(file_id), name, content_type, len(data), user_id),
    )
    return StoredFile(id=file_id, original_name=name, content_type=content_type, size_bytes=len(data))


def store_bytes(conn, user_id, name: str, content_type: str, data: bytes) -> UUID:
    if len(data) > settings.max_upload_bytes:
        raise ApiError(413, "file_too_large", "Файл больше 20 МБ")
    file_id = uuid4()
    path = _file_path(str(file_id))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    conn.execute(
        """
        INSERT INTO files (id, object_key, original_name, content_type, size_bytes, uploaded_by)
        VALUES (%s, %s, %s, %s, %s, %s)
        """,
        (file_id, str(file_id), name, content_type, len(data), user_id),
    )
    return file_id


def read_stored(conn, file_id) -> bytes:
    row = must(one(conn, "SELECT object_key FROM files WHERE id = %s", (file_id,)), "Файл не найден")
    path = _file_path(row["object_key"])
    if not path.is_file():
        raise not_found("Файл не найден")
    return path.read_bytes()


def _can_read_file(conn, user, file_id) -> bool:
    row = one(conn, "SELECT uploaded_by FROM files WHERE id = %s", (file_id,))
    if row is None:
        return False
    if row["uploaded_by"] == user.id:
        return True
    if one(conn, "SELECT 1 FROM student_profiles WHERE user_id = %s AND photo_file_id = %s", (user.id, file_id)):
        return True
    if one(
        conn,
        """
        SELECT 1 FROM portfolio_documents d
        LEFT JOIN portfolio_grants g ON g.document_id = d.id AND g.grantee_user_id = %s
        WHERE d.file_id = %s AND (d.student_user_id = %s OR g.grantee_user_id IS NOT NULL)
        """,
        (user.id, file_id, user.id),
    ):
        return True
    if one(
        conn,
        """
        SELECT 1 FROM certificate_requests
        WHERE result_file_id = %s AND student_user_id = %s
        """,
        (file_id, user.id),
    ):
        return True
    if "certificates.review" in user.permissions and one(
        conn,
        "SELECT 1 FROM certificate_requests WHERE result_file_id = %s",
        (file_id,),
    ):
        return True
    if one(
        conn,
        """
        SELECT 1
        FROM message_attachments a
        JOIN conversation_members m ON m.conversation_id = (
            SELECT conversation_id FROM messages WHERE id = a.message_id
        )
        WHERE a.file_id = %s AND m.user_id = %s
        """,
        (file_id, user.id),
    ):
        return True
    if "import.run" in user.permissions and one(
        conn,
        "SELECT 1 FROM import_batches WHERE stored_file_id = %s",
        (file_id,),
    ):
        return True
    if one(conn, "SELECT 1 FROM university WHERE id = 1 AND logo_file_id = %s", (file_id,)):
        return True
    return False


def open_file(conn, user, file_id) -> FileResponse:
    if not _can_read_file(conn, user, file_id):
        raise not_found("Файл не найден")
    row = must(one(conn, "SELECT * FROM files WHERE id = %s", (file_id,)))
    path = _file_path(row["object_key"])
    if not path.is_file():
        raise not_found("Файл не найден")
    return FileResponse(path, media_type=row["content_type"], filename=row["original_name"])


def open_logo(conn) -> FileResponse:
    row = load_university(conn)
    if row["logo_file_id"] is None:
        raise not_found("Логотип не загружен")
    stored = must(one(conn, "SELECT * FROM files WHERE id = %s", (row["logo_file_id"],)), "Логотип не загружен")
    path = _file_path(stored["object_key"])
    if not path.is_file():
        raise not_found("Логотип не загружен")
    return FileResponse(path, media_type=stored["content_type"], content_disposition_type="inline")


def list_notifications(conn, user, cursor: str | None, limit: int | None) -> NotificationPage:
    size = clamp_limit(limit)
    params: list = [user.id]
    clause = ""
    if cursor:
        moment, entity_id = decode_cursor(cursor)
        clause = "AND (created_at, id) < (%s, %s)"
        params.extend([moment, entity_id])
    params.append(size + 1)
    rows = many(
        conn,
        f"""
        SELECT id, type, title, body, payload, read_at, created_at
        FROM notifications
        WHERE user_id = %s {clause}
        ORDER BY created_at DESC, id DESC
        LIMIT %s
        """,
        tuple(params),
    )
    next_cursor = None
    if len(rows) > size:
        rows = rows[:size]
        last = rows[-1]
        next_cursor = encode_cursor(last["created_at"], last["id"])
    return NotificationPage(
        items=[
            Notification(
                id=row["id"],
                type=row["type"],
                title=row["title"],
                body=row["body"],
                read_at=row["read_at"],
                created_at=row["created_at"],
                payload=row["payload"] or {},
            )
            for row in rows
        ],
        next_cursor=next_cursor,
    )


def mark_notification(conn, user, notification_id) -> None:
    updated = conn.execute(
        """
        UPDATE notifications SET read_at = COALESCE(read_at, now())
        WHERE id = %s AND user_id = %s
        """,
        (notification_id, user.id),
    )
    if updated.rowcount == 0:
        raise not_found("Уведомление не найдено")


def mark_all_notifications(conn, user) -> None:
    conn.execute(
        "UPDATE notifications SET read_at = now() WHERE user_id = %s AND read_at IS NULL",
        (user.id,),
    )


def register_device(conn, user, platform: str, token: str) -> None:
    cleaned = token.strip()
    if not cleaned:
        raise invalid("empty_token", "Пустой токен устройства")
    conn.execute("DELETE FROM device_tokens WHERE token = %s AND user_id <> %s", (cleaned, user.id))
    conn.execute(
        """
        INSERT INTO device_tokens (user_id, platform, token)
        VALUES (%s, %s, %s)
        ON CONFLICT (user_id, token) DO UPDATE SET platform = EXCLUDED.platform
        """,
        (user.id, platform, cleaned),
    )


def _certificate(row) -> CertificateRequest:
    return CertificateRequest(
        id=row["id"],
        type_title=row["type_title"],
        delivery_mode=row["delivery_mode"],
        status=row["status"],
        comment=row["comment"],
        appointment_at=row["appointment_at"],
        result_file_id=row["result_file_id"],
        created_at=row["created_at"],
        student_id=row["student_user_id"],
        student_name=person(row) if row.get("last_name") else None,
    )


_CERT_SQL = """
    SELECT r.id, r.delivery_mode, r.status, r.comment, r.appointment_at, r.result_file_id,
           r.created_at, r.student_user_id, t.title AS type_title,
           u.last_name, u.first_name, u.middle_name
    FROM certificate_requests r
    JOIN certificate_types t ON t.id = r.type_id
    JOIN users u ON u.id = r.student_user_id
"""


def certificate_types(conn, user, include_disabled: bool = False) -> list[CertificateType]:
    if not include_disabled:
        require_section_for_student(conn, user, "certificates")
    clause = "" if include_disabled else "WHERE t.enabled"
    rows = many(
        conn,
        f"""
        SELECT t.id, t.code, t.title, t.enabled,
               COALESCE(array_agg(m.mode) FILTER (WHERE m.mode IS NOT NULL), ARRAY[]::certificate_delivery[]) AS modes
        FROM certificate_types t
        LEFT JOIN certificate_type_modes m ON m.type_id = t.id
        {clause}
        GROUP BY t.id
        ORDER BY t.sort_order, t.title
        """,
        (),
    )
    return [
        CertificateType(
            id=row["id"],
            code=row["code"],
            title=row["title"],
            enabled=row["enabled"],
            delivery_modes=list(row["modes"]),
        )
        for row in rows
    ]


def list_certificate_requests(conn, user, status: str | None) -> list[CertificateRequest]:
    params: list = []
    filters = []
    if user.role == "student" or "certificates.review" not in user.permissions:
        require_section_for_student(conn, user, "certificates")
        if user.role != "student":
            raise forbidden()
        filters.append("r.student_user_id = %s")
        params.append(user.id)
    if status:
        filters.append("r.status = %s")
        params.append(status)
    where = f"WHERE {' AND '.join(filters)}" if filters else ""
    return [_certificate(row) for row in many(conn, f"{_CERT_SQL} {where} ORDER BY r.created_at DESC", tuple(params))]


def create_certificate(conn, user, body) -> CertificateRequest:
    if user.role != "student":
        raise forbidden()
    require_section(conn, "certificates")
    kind = must(
        one(conn, "SELECT id, enabled FROM certificate_types WHERE id = %s", (body.type_id,)),
        "Вид справки не найден",
    )
    if not kind["enabled"]:
        raise invalid("type_disabled", "Этот вид справки сейчас не заказывают")
    row = conn.execute(
        """
        INSERT INTO certificate_requests (student_user_id, type_id, delivery_mode, comment)
        VALUES (%s, %s, %s, %s)
        RETURNING id
        """,
        (user.id, body.type_id, body.delivery_mode, body.comment),
    ).fetchone()
    return _certificate(must(one(conn, f"{_CERT_SQL} WHERE r.id = %s", (row["id"],))))


def update_certificate(conn, user, request_id, body) -> CertificateRequest:
    user.require("certificates.review")
    current = must(one(conn, "SELECT student_user_id FROM certificate_requests WHERE id = %s", (request_id,)))
    assignments = []
    values: list = []
    if body.status is not None:
        assignments.append("status = %s")
        values.append(body.status)
    if "appointment_at" in body.model_fields_set:
        assignments.append("appointment_at = %s")
        values.append(body.appointment_at)
    if body.comment is not None:
        assignments.append("comment = %s")
        values.append(body.comment)
    if "result_file_id" in body.model_fields_set:
        assignments.append("result_file_id = %s")
        values.append(body.result_file_id)
    assignments.append("assignee_user_id = %s")
    values.append(user.id)
    values.append(request_id)
    conn.execute(
        f"UPDATE certificate_requests SET {', '.join(assignments)} WHERE id = %s",
        tuple(values),
    )
    notify(conn, current["student_user_id"], "certificate_updated", "Заказ справки обновлён", payload={"requestId": str(request_id)})
    return _certificate(must(one(conn, f"{_CERT_SQL} WHERE r.id = %s", (request_id,))))


def _dorm(row) -> DormApplication:
    return DormApplication(
        id=row["id"],
        status=row["status"],
        building=row["building"],
        room=row["room"],
        comment=row["comment"],
        contract_id=row["contract_id"],
        created_at=row["created_at"],
        student_id=row["student_user_id"],
        student_name=person(row) if row.get("last_name") else None,
    )


_DORM_SQL = """
    SELECT a.id, a.status, a.building, a.room, a.comment, a.contract_id, a.created_at,
           a.student_user_id, u.last_name, u.first_name, u.middle_name
    FROM dorm_applications a
    JOIN users u ON u.id = a.student_user_id
"""


def list_dorms(conn, user) -> list[DormApplication]:
    if user.role == "student" or "dorm.review" not in user.permissions:
        if user.role != "student":
            raise forbidden()
        require_section(conn, "dormitory")
        rows = many(conn, f"{_DORM_SQL} WHERE a.student_user_id = %s ORDER BY a.created_at DESC", (user.id,))
    else:
        rows = many(conn, f"{_DORM_SQL} ORDER BY a.created_at DESC")
    return [_dorm(row) for row in rows]


def create_dorm(conn, user, comment: str) -> DormApplication:
    if user.role != "student":
        raise forbidden()
    require_section(conn, "dormitory")
    open_one = one(
        conn,
        """
        SELECT 1 FROM dorm_applications
        WHERE student_user_id = %s AND status IN ('pending', 'in_progress')
        """,
        (user.id,),
    )
    if open_one:
        raise invalid("dorm_open", "У вас уже есть заявление на рассмотрении")
    row = conn.execute(
        """
        INSERT INTO dorm_applications (student_user_id, comment)
        VALUES (%s, %s)
        RETURNING id
        """,
        (user.id, comment),
    ).fetchone()
    return _dorm(must(one(conn, f"{_DORM_SQL} WHERE a.id = %s", (row["id"],))))


def update_dorm(conn, user, application_id, body) -> DormApplication:
    user.require("dorm.review")
    current = must(one(conn, "SELECT student_user_id, status FROM dorm_applications WHERE id = %s", (application_id,)))
    assignments = []
    values: list = []
    status = body.status
    if status is not None:
        assignments.append("status = %s")
        values.append(status)
    if body.building is not None:
        assignments.append("building = %s")
        values.append(body.building)
    if body.room is not None:
        assignments.append("room = %s")
        values.append(body.room)
    if "contract_id" in body.model_fields_set:
        assignments.append("contract_id = %s")
        values.append(body.contract_id)
    if body.comment is not None:
        assignments.append("comment = %s")
        values.append(body.comment)
    assignments.append("assignee_user_id = %s")
    values.append(user.id)
    values.append(application_id)
    conn.execute(f"UPDATE dorm_applications SET {', '.join(assignments)} WHERE id = %s", tuple(values))
    if status == "settled":
        conn.execute(
            "UPDATE student_profiles SET lives_in_dorm = true WHERE user_id = %s",
            (current["student_user_id"],),
        )
    notify(conn, current["student_user_id"], "dorm_updated", "Заявление на общежитие обновлено", payload={"applicationId": str(application_id)})
    return _dorm(must(one(conn, f"{_DORM_SQL} WHERE a.id = %s", (application_id,))))


def _ledger(row) -> LedgerEntry:
    return LedgerEntry(
        id=row["id"],
        direction=row["direction"],
        amount=money(row["amount"]),
        occurred_on=row["occurred_on"],
        description=row["description"],
        reversed=row["reversed"],
        reverses_entry_id=row["reverses_entry_id"],
    )


def _demo(row) -> DemoPayment:
    return DemoPayment(id=row["id"], method=row["method"], amount=money(row["amount"]), message=DEMO_MESSAGE)


def _contract(conn, row, with_entries: bool) -> Contract:
    entries = None
    demos = None
    if with_entries:
        entries = [
            _ledger(item)
            for item in many(
                conn,
                """
                SELECT e.id, e.direction, e.amount, e.occurred_on, e.description, e.reverses_entry_id,
                       (e.reverses_entry_id IS NOT NULL OR EXISTS (
                           SELECT 1 FROM ledger_entries reversal WHERE reversal.reverses_entry_id = e.id
                       )) AS reversed
                FROM ledger_entries e
                WHERE e.contract_id = %s
                ORDER BY e.occurred_on, e.created_at
                """,
                (row["id"],),
            )
        ]
        demos = [
            _demo(item)
            for item in many(
                conn,
                """
                SELECT id, method, amount FROM demo_payments
                WHERE contract_id = %s ORDER BY created_at
                """,
                (row["id"],),
            )
        ]
    return Contract(
        id=row["id"],
        kind=row["kind"],
        number=row["number"],
        title=row["title"],
        charged=money(row["charged"]),
        paid=money(row["paid"]),
        debt=money(row["debt"]),
        student_id=row["student_user_id"],
        entries=entries,
        demo_payments=demos,
    )


_CONTRACT_SQL = """
    SELECT c.id, c.kind, c.number, c.title, c.student_user_id,
           COALESCE(b.charged, 0) AS charged,
           COALESCE(b.paid, 0) AS paid,
           COALESCE(b.debt, 0) AS debt
    FROM contracts c
    LEFT JOIN contract_balances b ON b.contract_id = c.id
"""


def list_contracts(conn, user, student_id=None) -> list[Contract]:
    if user.role == "student":
        require_section(conn, "contracts")
        rows = many(conn, f"{_CONTRACT_SQL} WHERE c.student_user_id = %s ORDER BY c.created_at", (user.id,))
    elif "contracts.manage" in user.permissions:
        if student_id is not None:
            rows = many(conn, f"{_CONTRACT_SQL} WHERE c.student_user_id = %s ORDER BY c.created_at", (student_id,))
        else:
            rows = many(conn, f"{_CONTRACT_SQL} ORDER BY c.created_at DESC")
    else:
        raise forbidden()
    return [_contract(conn, row, with_entries=False) for row in rows]


def get_contract(conn, user, contract_id) -> Contract:
    row = must(one(conn, f"{_CONTRACT_SQL} WHERE c.id = %s", (contract_id,)), "Договор не найден")
    if user.role == "student":
        require_section(conn, "contracts")
        if row["student_user_id"] != user.id:
            raise not_found("Договор не найден")
    elif "contracts.manage" not in user.permissions:
        raise forbidden()
    return _contract(conn, row, with_entries=True)


def create_demo_payment(conn, user, contract_id, body) -> DemoPayment:
    if user.role != "student":
        raise forbidden("Учебную оплату проводит студент по своему договору")
    require_section(conn, "contracts")
    contract = must(one(conn, "SELECT student_user_id FROM contracts WHERE id = %s", (contract_id,)), "Договор не найден")
    if contract["student_user_id"] != user.id:
        raise not_found("Договор не найден")
    amount = parse_amount(body.amount)
    row = conn.execute(
        """
        INSERT INTO demo_payments (contract_id, student_user_id, amount, method)
        VALUES (%s, %s, %s, %s)
        RETURNING id
        """,
        (contract_id, user.id, amount, body.method),
    ).fetchone()
    notify(
        conn,
        user.id,
        "demo_payment_recorded",
        "Демо-оплата выполнена",
        DEMO_MESSAGE,
        {"contractId": str(contract_id), "demoPaymentId": str(row["id"])},
    )
    return DemoPayment(id=row["id"], method=body.method, amount=money(amount), message=DEMO_MESSAGE)


def _portfolio(conn, row) -> PortfolioDocument:
    grants = many(conn, "SELECT grantee_user_id FROM portfolio_grants WHERE document_id = %s", (row["id"],))
    return PortfolioDocument(
        id=row["id"],
        kind=row["kind"],
        title=row["title"],
        body=row["body"],
        file_id=row["file_id"],
        grantee_user_ids=[item["grantee_user_id"] for item in grants],
    )


def list_portfolio(conn, user) -> list[PortfolioDocument]:
    if user.role == "student":
        require_section(conn, "portfolio")
    rows = many(
        conn,
        """
        SELECT DISTINCT d.id, d.kind, d.title, d.body, d.file_id, d.created_at
        FROM portfolio_documents d
        LEFT JOIN portfolio_grants g ON g.document_id = d.id AND g.grantee_user_id = %s
        WHERE d.student_user_id = %s OR g.grantee_user_id IS NOT NULL
        ORDER BY d.created_at DESC
        """,
        (user.id, user.id),
    )
    return [_portfolio(conn, row) for row in rows]


def create_portfolio(conn, user, body) -> PortfolioDocument:
    if user.role != "student":
        raise forbidden()
    require_section(conn, "portfolio")
    row = conn.execute(
        """
        INSERT INTO portfolio_documents (student_user_id, kind, title, body, file_id)
        VALUES (%s, %s, %s, %s, %s)
        RETURNING id, kind, title, body, file_id
        """,
        (user.id, body.kind, body.title.strip(), body.body, body.file_id),
    ).fetchone()
    return _portfolio(conn, row)


def _own_document(conn, user, document_id):
    row = must(one(conn, "SELECT * FROM portfolio_documents WHERE id = %s", (document_id,)), "Документ не найден")
    if row["student_user_id"] != user.id:
        raise forbidden("Чужой документ меняет только владелец")
    return row


def update_portfolio(conn, user, document_id, body) -> PortfolioDocument:
    _own_document(conn, user, document_id)
    conn.execute(
        """
        UPDATE portfolio_documents
        SET kind = %s, title = %s, body = %s, file_id = %s
        WHERE id = %s
        """,
        (body.kind, body.title.strip(), body.body, body.file_id, document_id),
    )
    return _portfolio(conn, must(one(conn, "SELECT * FROM portfolio_documents WHERE id = %s", (document_id,))))


def delete_portfolio(conn, user, document_id) -> None:
    _own_document(conn, user, document_id)
    conn.execute("DELETE FROM portfolio_documents WHERE id = %s", (document_id,))


def replace_grants(conn, user, document_id, user_ids: list[UUID]) -> PortfolioDocument:
    _own_document(conn, user, document_id)
    unique_ids = []
    for grantee in user_ids:
        if grantee == user.id or grantee in unique_ids:
            continue
        if one(conn, "SELECT 1 FROM users WHERE id = %s", (grantee,)) is None:
            raise invalid("unknown_user", "В списке доступа есть неизвестный пользователь")
        unique_ids.append(grantee)
    conn.execute("DELETE FROM portfolio_grants WHERE document_id = %s", (document_id,))
    for grantee in unique_ids:
        conn.execute(
            "INSERT INTO portfolio_grants (document_id, grantee_user_id) VALUES (%s, %s)",
            (document_id, grantee),
        )
    return _portfolio(conn, must(one(conn, "SELECT * FROM portfolio_documents WHERE id = %s", (document_id,))))
