from decimal import Decimal


def score_finals(finals: list[tuple[Decimal | None, Decimal]], definition: dict) -> Decimal | None:
    """Итог по формуле. finals — пары (балл, кредиты) только итоговых оценок."""
    if definition.get("of") != "final_numeric_grades":
        return None
    scored = [(Decimal(score), Decimal(credits)) for score, credits in finals if score is not None]
    if not scored:
        return None
    kind = definition.get("type")
    if kind == "mean":
        return sum((score for score, _ in scored), Decimal(0)) / Decimal(len(scored))
    if kind == "sum":
        return sum((score for score, _ in scored), Decimal(0))
    if kind == "weighted_average":
        weighted = [(score, credits) for score, credits in scored if credits > 0]
        total = sum((credits for _, credits in weighted), Decimal(0))
        if total == 0:
            return None
        return sum((score * credits for score, credits in weighted), Decimal(0)) / total
    return None


def recompute_student(conn, student_id) -> None:
    formula = conn.execute(
        "SELECT id, definition FROM rating_formulas WHERE is_active"
    ).fetchone()
    if formula is None:
        conn.execute("DELETE FROM rating_snapshots WHERE student_user_id = %s", (student_id,))
        return
    rows = conn.execute(
        """
        SELECT score, credits
        FROM grades
        WHERE student_user_id = %s AND is_final AND score IS NOT NULL
        """,
        (student_id,),
    ).fetchall()
    value = score_finals([(row["score"], row["credits"]) for row in rows], formula["definition"])
    if value is None:
        conn.execute("DELETE FROM rating_snapshots WHERE student_user_id = %s", (student_id,))
        return
    conn.execute(
        """
        INSERT INTO rating_snapshots (student_user_id, formula_id, score)
        VALUES (%s, %s, %s)
        ON CONFLICT (student_user_id) DO UPDATE
        SET formula_id = EXCLUDED.formula_id,
            score = EXCLUDED.score,
            computed_at = now()
        """,
        (student_id, formula["id"], value.quantize(Decimal("0.001"))),
    )
