import base64
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from app.errors import invalid


def full_name(last_name: str, first_name: str, middle_name: str | None = None) -> str:
    parts = [last_name, first_name, middle_name or ""]
    return " ".join(part for part in parts if part)


def money(value: Decimal | int | None) -> str:
    return decimal_str(value, "0.01")


def decimal_str(value: Decimal | int | None, quant: str = "0.01") -> str:
    amount = Decimal(value or 0).quantize(Decimal(quant))
    return format(amount, "f")


def encode_cursor(moment: datetime, entity_id: UUID | str) -> str:
    raw = f"{moment.isoformat()}|{entity_id}".encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def decode_cursor(value: str) -> tuple[datetime, str]:
    padded = value + "=" * (-len(value) % 4)
    try:
        text = base64.urlsafe_b64decode(padded.encode()).decode()
        stamp, entity_id = text.split("|", 1)
        return datetime.fromisoformat(stamp), entity_id
    except (ValueError, UnicodeError) as exc:
        raise invalid("bad_cursor", "Некорректная страница списка") from exc
