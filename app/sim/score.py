"""Player score from choices. Starts at the opening resilience (0-100) and stays in that range.

The opening value is the financial resilience plus a bounded adjustment from the
onboarding quiz (risk answer versus the goal horizon, insurance, dependents, and the
statement score and risk signals when one was uploaded).
Each choice adds a delta from how it compares with the other options. The size of that
delta is inversely proportional to the goal horizon: a short goal moves more points per
choice, so a few months and a few years can both reach a high or a low score.
Agents still judge a choice from -10 to +10; the game scales that note the same way.
A later call from the same agent replaces its previous one. The sum is clamped to 0-100.
"""
import time

from . import engine as E

LO = 0
HI = 100
# A 12-month goal keeps the original swing: best choice +8, worst -8, agent note ±10.
REFERENCE_MONTHS = 12
CHOICE_SPAN = 8
AGENT_SPAN = 10
MAX_SPAN = 48
AGENTS = ("angel", "investments", "business")


class ScoreError(ValueError):
    pass


def quiz_points(profile) -> int:
    """How the onboarding answers move the opening score, capped at ±20.

    The money picture is already in the resilience score. This adds the quiz itself:
    whether the risk answer fits the goal, plus insurance, dependents and, when the
    player uploaded a statement, its stability score and risk signals.
    """
    if profile is None:
        return 0
    horizon = max(1, int(profile.goal.horizon_months))
    risk = str(profile.risk_tolerance or "").strip().lower()
    if horizon <= 24:
        fit = {"scazuta": 6, "medie": 2, "ridicata": -6}
    elif horizon <= 48:
        fit = {"scazuta": 2, "medie": 6, "ridicata": 2}
    else:
        fit = {"scazuta": -2, "medie": 4, "ridicata": 6}
    points = float(fit.get(risk, 0))
    if profile.health.insured:
        points += 4
    points -= min(6, 2 * max(0, int(profile.dependents)))
    source = profile.source
    if source.statement_score is not None:
        nudge = E.round_half_away((int(source.statement_score) - 50) / 10.0)
        points += max(-8.0, min(8.0, nudge))
    points -= min(8, 2 * len(source.risk_signals or []))
    return int(max(-20, min(20, E.round_half_away(points))))


def initial(sim: E.SimState, profile=None) -> int:
    return clamp(E.resilience_score(sim) + quiz_points(profile))


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


def goal_months(session) -> int:
    profile = getattr(session, "profile", None)
    goal = getattr(profile, "goal", None)
    try:
        months = int(getattr(goal, "horizon_months", REFERENCE_MONTHS))
    except (TypeError, ValueError):
        return REFERENCE_MONTHS
    return months if months >= 1 else REFERENCE_MONTHS


def choice_span(months: int) -> int:
    """Points a best-or-worst choice is worth. Shorter goals are worth more per choice."""
    months = max(1, int(months))
    scaled = E.round_half_away(CHOICE_SPAN * REFERENCE_MONTHS / months)
    return int(max(1, min(MAX_SPAN, scaled)))


def scale_points(base: float, months: int) -> int:
    """Map a 12-month point value onto this goal's horizon."""
    return int(E.round_half_away(float(base) * choice_span(months) / CHOICE_SPAN))


def automatic_delta(chosen: dict | None, options: list[dict], span: int = CHOICE_SPAN) -> tuple[int, str]:
    """Where the chosen option sits between the worst (-span) and the best (+span)."""
    span = max(1, int(span))
    options = options or [chosen or {}]
    scores = [option_points(item) for item in options]
    mine = option_points(chosen)
    if len(scores) == 1:
        delta = int(E.round_half_away(mine * span / CHOICE_SPAN))
        delta = max(-span, min(span, delta))
        return delta, "Singura variantă disponibilă."
    best, worst = max(scores), min(scores)
    if abs(best - worst) < 1e-9:
        return 0, "Variantele sunt echivalente pentru scor."
    position = (mine - worst) / (best - worst)
    delta = int(E.round_half_away(position * (2 * span) - span))
    delta = max(-span, min(span, delta))
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
    profile = getattr(session, "profile", None)
    session.score_quiz = quiz_points(profile)
    session.score_initial = clamp(E.resilience_score(sim) + session.score_quiz)
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
    months = goal_months(session)
    span = choice_span(months)
    delta, reason = automatic_delta(chosen_ops, option_ops, span)
    return _append(session, institution=institution, action_id=action_id, option_id=option_id,
                   title=title, label=label, delta=delta, reason=reason, span=span, horizon_months=months)


def record_free(session, *, institution: str, action_id: str, amount: float) -> dict:
    base, reason = free_delta(action_id, amount)
    months = goal_months(session)
    delta = scale_points(base, months)
    labels = {
        "save": "Mut în economii",
        "invest": "Investesc",
        "repay": "Rambursez din datorie",
        "set_monthly_saving": "Economie lunară automată",
        "set_monthly_invest": "Investiție lunară automată",
    }
    return _append(session, institution=institution, action_id=action_id, option_id=action_id,
                   title=labels.get(action_id, action_id), label=f"{amount:.0f} lei", delta=delta, reason=reason,
                   span=choice_span(months), horizon_months=months)


def public(session) -> dict | None:
    if session.score_initial is None:
        return None
    adjustments = session.score_adjustments
    return {
        "valoare": current(session),
        "initial": session.score_initial,
        "din_quiz": int(getattr(session, "score_quiz", 0) or 0),
        "interval": [LO, HI],
        "orizont_luni": goal_months(session),
        "amplitudine": choice_span(goal_months(session)),
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
    requested = _delta(delta)
    points = scale_points(requested, goal_months(session))
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
        "delta_cerut": requested,
        "delta_aplicat": applied,
        "interval": [LO, HI],
        "summary": (f"Scor {after}/100 (nota {requested:+d} valorează {points:+d} pe orizontul obiectivului, "
                    f"aplicat {applied:+d}). Scorul rămâne între 0 și 100."),
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
        "minus dacă le înrăutățește. Jocul scalează nota după orizontul obiectivului: aceeași notă adaugă sau "
        "scade mai multe puncte când obiectivul e pe puține luni. Apelul tău înlocuiește evaluarea anterioară "
        "a aceluiași agent pentru aceeași alegere. Dacă suma nu încape în 0-100, se taie și primești delta_aplicat.",
        {"type": "object", "properties": {
            "choice_id": {"type": "string", "description": "id-ul din scor.alegeri"},
            "delta": {"type": "integer", "minimum": -AGENT_SPAN, "maximum": AGENT_SPAN},
            "reason": {"type": "string", "description": "motiv scurt, în română"},
        }, "required": ["choice_id", "delta", "reason"]},
        add_to_score,
    )
