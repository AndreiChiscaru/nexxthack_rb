"""Shared API contracts (docs/implementation-plan.md §4). Field names must match the plan exactly."""
from typing import Any, Literal

from pydantic import BaseModel, Field

Institution = Literal["home", "market", "education", "work", "business", "hospital", "bank"]
INSTITUTIONS: tuple[str, ...] = ("home", "market", "education", "work", "business", "hospital", "bank")


# --- §4.1 Profile -----------------------------------------------------------

class Goal(BaseModel):
    type: str
    description: str = ""
    target_amount: float
    horizon_months: int


class Income(BaseModel):
    salary: float
    other: float = 0


class Recurring(BaseModel):
    rent: float = 0
    utilities: float = 0
    subscriptions: float = 0
    transport: float = 0


class Spending(BaseModel):
    food: float = 0
    leisure: float = 0


class Debt(BaseModel):
    name: str
    monthly: float
    remaining: float
    apr: float


class Education(BaseModel):
    status: str = ""
    scholarship: float = 0
    tuition_monthly: float = 0


class Health(BaseModel):
    insured: bool = False


class ProfileSource(BaseModel):
    statement_uploaded: bool = False
    statement_score: int | None = None
    risk_signals: list[str] = Field(default_factory=list)


class Profile(BaseModel):
    name: str = ""
    age: int
    goal: Goal
    income: Income
    recurring: Recurring
    spending: Spending = Field(default_factory=Spending)
    savings: float
    investments: float = 0
    cash: float = 0
    debts: list[Debt]
    education: Education = Field(default_factory=Education)
    health: Health = Field(default_factory=Health)
    business_interest: bool = False
    risk_tolerance: str
    dependents: int = 0
    source: ProfileSource = Field(default_factory=ProfileSource)


# --- §4.2 Game state --------------------------------------------------------

class GoalProgress(BaseModel):
    type: str
    target_amount: float
    progress: float
    on_track: bool


class Balance(BaseModel):
    cash: float
    savings: float
    investments: float
    debt: float
    net_worth: float


class MonthlyExpenses(BaseModel):
    home: float = 0
    market: float = 0
    education: float = 0
    health: float = 0
    business: float = 0
    bank: float = 0


class Monthly(BaseModel):
    income: float
    expenses: MonthlyExpenses


class Wellbeing(BaseModel):
    stress: float
    confidence: float


class InstitutionStatus(BaseModel):
    id: Institution
    pending_events: int


class ProductHolding(BaseModel):
    id: str
    balance: float


class LogEntry(BaseModel):
    month: int
    institution: Institution
    text: str


class GameState(BaseModel):
    session_id: str
    month: int
    age: int
    goal: GoalProgress
    balance: Balance
    monthly: Monthly
    wellbeing: Wellbeing
    institutions: list[InstitutionStatus]
    products: list[ProductHolding]
    log: list[LogEntry]


# --- §4.4 Events ------------------------------------------------------------

class EventOption(BaseModel):
    id: str
    label: str
    # Same vocabulary as finance_sim.gd (spend, loan, salary_mult, living_add, mood, ...).
    ops: dict[str, Any]


class Event(BaseModel):
    id: str
    institution: Institution
    title: str
    text: str
    options: list[EventOption]


# --- Shared -----------------------------------------------------------------

class ToolCall(BaseModel):
    name: str
    args: dict[str, Any]
    summary: str


class Product(BaseModel):
    """Same shape as raiffquest/scripts/raiff/catalog.gd."""
    id: str
    category: str
    name: str
    apr: float
    min_months: int
    max_months: int
    note: str
    mock: bool = True


# --- Requests / responses (§4.3) ---------------------------------------------

class SessionResponse(BaseModel):
    session_id: str


class OnboardingMessageRequest(BaseModel):
    session_id: str
    text: str


class OnboardingMessageResponse(BaseModel):
    reply: str
    missing_fields: list[str]
    done: bool
    profile: Profile | None = None


class StatementResponse(BaseModel):
    analysis: dict[str, Any]
    profile_fields: dict[str, Any]
    missing_fields: list[str]


class GameStartRequest(BaseModel):
    session_id: str
    profile: Profile | None = None


class GameStartResponse(BaseModel):
    state: GameState
    events: list[Event]


class GameActionRequest(BaseModel):
    session_id: str
    institution: Institution
    action_id: str
    params: dict[str, Any] = Field(default_factory=dict)


class GameActionResponse(BaseModel):
    state: GameState
    delta: dict[str, float]
    advisor_note: str


class GameAdvanceRequest(BaseModel):
    session_id: str


class GameAdvanceResponse(BaseModel):
    state: GameState
    events: list[Event]


class ChatRequest(BaseModel):
    session_id: str
    text: str


class ChatResponse(BaseModel):
    reply: str
    tool_calls: list[ToolCall]


class ProductsResponse(BaseModel):
    products: list[Product]
