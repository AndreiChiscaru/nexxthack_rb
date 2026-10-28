"""Player score from choices. Starts at the opening resilience (0-100) and stays in that range.

Each choice adds a bounded delta from how it compares with the other options.
Each agent may add one delta per choice, between -10 and +10; a later call from the
same agent replaces its previous one. The sum is clamped to 0-100.
"""
import time

from . import engine as E

LO = 0
HI = 100
CHOICE_SPAN = 8
AGENT_SPAN = 10
AGENTS = ("angel", "investments", "business")


class ScoreError(ValueError):
    pass


def initial(sim: E.SimState) -> int:
    return E.resilience_score(sim)


def clamp(value: float) -> int:
    return int(max(LO, min(HI, E.round_half_away(value))))


def option_points(ops: dict | None) -> float:
    """Higher means the option looks healthier: less debt, less spend, more saving."""
    ops = ops or {}
    points = 0.0
    living = ops.get("living_add")
    if living is not None:
        points += -float(living) / 100.0
    if float(ops.get("emergency_contrib") or 0) > 0:
        points += 4
    if float(ops.get("invest_contrib") or 0) > 0:
        points += 3
    salary_add = ops.get("salary_add")
    if salary_add is not None and float(salary_add) > 0:
        points += 3
    salary_mult = ops.get("salary_mult")
    if salary_mult is not None and float(salary_mult) > 1:
        points += 3
    side = ops.get("side_income_add")
    if side is not None and float(side) > 0:
        points += 3
    loan = ops.get("loan")
    if isinstance(loan, dict):
        points -= 4 + float(loan.get("apr") or 0) * 10
    spend = ops.get("spend")
    if spend is not None:
        points -= min(6.0, float(spend) / 500.0)
    if "fiscal_pay" in ops:
        points += 6
    if "fiscal_late" in ops:
        points -= 8
    bonus = ops.get("bonus") or {}
    if isinstance(bonus, dict):
        mode = bonus.get("mode")
        if mode in ("prepay", "fund", "safe"):
            points += 4
        elif mode == "spend":
            points -= 3
    level = ops.get("insurance_level")
    if level is not None and int(level) > 0:
        points += 2
    mood = ops.get("mood") or {}
    if isinstance(mood, dict):
        points += float(mood.get("conf") or 0) / 20.0
        points -= float(mood.get("stress") or 0) / 20.0
    return points


def automatic_delta(chosen: dict | None, options: list[dict]) -> tuple[int, str]:
    """Where the chosen option sits between the worst (-8) and the best (+8)."""
    options = options or [chosen or {}]
    scores = [option_points(item) for item in options]
    mine = option_points(chosen)
    if len(scores) == 1:
        delta = max(-CHOICE_SPAN, min(CHOICE_SPAN, int(E.round_half_away(mine))))
        return delta, "Singura variantă disponibilă."
    best, worst = max(scores), min(scores)
    if abs(best - worst) < 1e-9:
        return 0, "Variantele sunt echivalente pentru scor."
    position = (mine - worst) / (best - worst)
    delta = int(E.round_half_away(position * (2 * CHOICE_SPAN) - CHOICE_SPAN))
    delta = max(-CHOICE_SPAN, min(CHOICE_SPAN, delta))
    if delta > 0:
        reason = "Alegerea e mai bună financiar decât celelalte variante."
    elif delta < 0:
        reason = "Alegerea e mai slabă financiar decât celelalte variante."
    else:
        reason = "Alegerea e la mijloc față de celelalte variante."
    return delta, reason


def free_delta(action_id: str, amount: float) -> tuple[int, str]:
    if action_id == "save":
        return 5, "Ai mutat bani în economii."
    if action_id == "invest":
        return 4, "Ai pus bani în investiții."
    if action_id == "repay":
        return 6, "Ai redus datoria."
    if action_id == "set_monthly_saving":
        if amount > 0:
            return 5, "Ai pornit o economie lunară automată."
        return -3, "Ai oprit economia lunară automată."
    if action_id == "set_monthly_invest":
        if amount > 0:
            return 4, "Ai pornit o investiție lunară automată."
        return -2, "Ai oprit investiția lunară automată."
    return 0, "Acțiune fără efect asupra scorului."


def value(initial_score: int, choices: list[dict], adjustments: list[dict]) -> int:
    raw = initial_score + sum(int(choice["delta"]) for choice in choices) + sum(int(item["delta"]) for item in adjustments)
    return clamp(raw)


def current(session) -> int:
    if session.score_initial is None:
        return 0
    return value(session.score_initial, session.choices, session.score_adjustments)


def reset(session, sim: E.SimState) -> int:
    session.choices = []
    session.score_adjustments = []
    session.score_initial = initial(sim)
    return session.score_initial


def _append(session, **fields) -> dict:
    choice = {
        "id": f"m{session.month}-{fields['action_id']}-{fields['option_id']}-{len(session.choices) + 1}",
        "month": session.month,
        **fields,
    }
    session.choices.append(choice)
    return choice


def record_choice(session, *, institution: str, action_id: str, option_id: str, title: str, label: str,
                  chosen_ops: dict, option_ops: list[dict]) -> dict:
    delta, reason = automatic_delta(chosen_ops, option_ops)
    return _append(session, institution=institution, action_id=action_id, option_id=option_id,
                   title=title, label=label, delta=delta, reason=reason)


def record_free(session, *, institution: str, action_id: str, amount: float) -> dict:
    delta, reason = free_delta(action_id, amount)
    labels = {
        "save": "Mut în economii",
        "invest": "Investesc",
        "repay": "Rambursez din datorie",
        "set_monthly_saving": "Economie lunară automată",
        "set_monthly_invest": "Investiție lunară automată",
    }
    return _append(session, institution=institution, action_id=action_id, option_id=action_id,
                   title=labels.get(action_id, action_id), label=f"{amount:.0f} lei", delta=delta, reason=reason)


def public(session) -> dict | None:
    if session.score_initial is None:
        return None
    adjustments = session.score_adjustments
    return {
        "valoare": current(session),
        "initial": session.score_initial,
        "interval": [LO, HI],
        "alegeri": [
            {
                "id": choice["id"],
                "luna": choice["month"],
                "titlu": choice["title"],
                "optiune": choice["label"],
                "delta_automat": choice["delta"],
                "motiv_automat": choice["reason"],
                "ajustari": [
                    {"agent": item["agent"], "delta": item["delta"], "motiv": item["reason"]}
                    for item in adjustments if item["choice_id"] == choice["id"]
                ],
            }
            for choice in session.choices
        ],
    }


def _delta(delta) -> int:
    if isinstance(delta, bool) or isinstance(delta, str):
        raise ScoreError(f"delta trebuie să fie un întreg între -{AGENT_SPAN} și {AGENT_SPAN}.")
    if isinstance(delta, float):
        if not delta.is_integer():
            raise ScoreError(f"delta trebuie să fie un întreg între -{AGENT_SPAN} și {AGENT_SPAN}.")
        delta = int(delta)
    if not isinstance(delta, int) or delta < -AGENT_SPAN or delta > AGENT_SPAN:
        raise ScoreError(f"delta trebuie să fie un întreg între -{AGENT_SPAN} și {AGENT_SPAN}.")
    return delta


def add(session, agent: str, choice_id: str, delta, reason: str) -> dict:
    """Replace this agent's previous note on the choice, then clamp the total to 0-100."""
    if session.sim is None or session.score_initial is None:
        raise ScoreError("Jocul nu a pornit încă.")
    if agent not in AGENTS:
        raise ScoreError("Agent necunoscut.")
    text = str(reason or "").strip()
    if not text or len(text) > 240:
        raise ScoreError("Motivul trebuie să aibă între 1 și 240 de caractere.")
    points = _delta(delta)
    if not any(choice["id"] == choice_id for choice in session.choices):
        raise ScoreError("Alegerea nu există. Folosește id-ul din lista de alegeri.")
    before = current(session)
    session.score_adjustments = [
        item for item in session.score_adjustments
        if not (item["agent"] == agent and item["choice_id"] == choice_id)
    ]
    session.score_adjustments.append({
        "agent": agent, "choice_id": choice_id, "delta": points, "reason": text,
    })
    after = current(session)
    applied = after - before
    return {
        "scor": after,
        "inainte": before,
        "delta_cerut": points,
        "delta_aplicat": applied,
        "interval": [LO, HI],
        "summary": (f"Scor {after}/100 (cerut {points:+d}, aplicat {applied:+d}). "
                    "Scorul rămâne între 0 și 100."),
    }


def tool(session_id: str, agent: str):
    """One tool, stamped with the calling agent so the model cannot score as someone else."""
    from ..agents.llm import Tool
    from ..sessions import find_session

    def add_to_score(choice_id: str, delta: int, reason: str):
        started = time.perf_counter()
        summary, status = "", "error"
        session = find_session(session_id)
        try:
            if session is None:
                raise ScoreError("Sesiune inexistentă.")
            result = add(session, agent, choice_id, delta, reason)
            summary, status = result["summary"], "ok"
            return result
        except ScoreError as exc:
            summary = f"eroare: {exc}"
            raise
        finally:
            if session is not None:
                session.tool_log.append({
                    "name": "add_to_score",
                    "args": {"choice_id": choice_id, "delta": delta, "reason": reason},
                    "summary": summary,
                    "duration_ms": round((time.perf_counter() - started) * 1000, 1),
                })

    return Tool(
        "add_to_score",
        "Adaugă la scorul jucătorului (0-100) pentru o alegere deja făcută. "
        f"delta este un întreg între -{AGENT_SPAN} și {AGENT_SPAN}: plus dacă alegerea ajută scopul și reziliența, "
        "minus dacă le înrăutățește. Apelul tău înlocuiește evaluarea anterioară a aceluiași agent pentru aceeași alegere. "
        "Dacă suma nu încape în 0-100, se taie și primești delta_aplicat.",
        {"type": "object", "properties": {
            "choice_id": {"type": "string", "description": "id-ul din scor.alegeri"},
            "delta": {"type": "integer", "minimum": -AGENT_SPAN, "maximum": AGENT_SPAN},
            "reason": {"type": "string", "description": "motiv scurt, în română"},
        }, "required": ["choice_id", "delta", "reason"]},
        add_to_score,
    )
