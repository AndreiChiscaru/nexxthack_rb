"""Raiffeisen product catalog (data/products.json) and time-limited campaigns (data/campaigns.json).

Both files are validated once at import, so the app fails fast on bad data. data/products.json keeps the
shape the consultant agent (app/agents/consultant.py) reads; as_of_date and disclaimer are optional there
and default to the catalog's date and the standard disclaimer.
"""
import json
from datetime import date
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, ValidationError, model_validator

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
PRODUCTS_PATH = DATA_DIR / "products.json"
CAMPAIGNS_PATH = DATA_DIR / "campaigns.json"

# Date of the public offer the catalog was built from (same date the consultant's prompt states).
CATALOG_AS_OF = date(2026, 10, 28)
DEFAULT_DISCLAIMER = (
    "Informații publice Raiffeisen Bank, cu titlu educativ. Dobânzile la credite sunt „de la” (minime) și nu sunt "
    "garantate: costul final îl stabilește banca după analiza dosarului. Dobânzile la economii sunt brute și se pot modifica."
)

CATALOG_CATEGORIES = ("credit", "locuinta", "economii", "cont", "card", "investitii", "pensie", "asigurare")
# Campaigns still live in products.json under this category because the consultant searches them there;
# the API serves them from data/campaigns.json (with end dates) and keeps them out of /api/products.
LEGACY_CAMPAIGN_CATEGORY = "campanie"
Category = Literal["credit", "locuinta", "economii", "cont", "card", "investitii", "pensie", "asigurare", "campanie"]


class CatalogError(ValueError):
    pass


class _Entry(BaseModel):
    # Unknown keys a teammate adds to the JSON are ignored rather than blocking startup.
    model_config = ConfigDict(extra="ignore")


class Product(_Entry):
    id: str = Field(pattern=r"^[a-z0-9_]+$")
    category: Category
    name: str = Field(min_length=1)
    terms: str = Field(min_length=1)
    conditions: str
    best_for: str
    cautions: str
    as_of_date: date = CATALOG_AS_OF
    disclaimer: str = DEFAULT_DISCLAIMER


class Campaign(_Entry):
    id: str = Field(pattern=r"^[a-z0-9_]+$")
    name: str = Field(min_length=1)
    terms: str = Field(min_length=1)
    conditions: str
    best_for: str
    cautions: str
    start_date: date | None = None
    end_date: date
    product_id: str | None = None  # related catalog product, if any
    as_of_date: date = CATALOG_AS_OF
    disclaimer: str = DEFAULT_DISCLAIMER

    @model_validator(mode="after")
    def _dates(self):
        if self.start_date and self.start_date > self.end_date:
            raise ValueError(f"campaign '{self.id}' ends before it starts")
        return self


def validate_entries(raw: list, model: type[BaseModel] = None, source: str = "catalog") -> dict:
    """Validates a JSON list of products (or campaigns); raises CatalogError on bad fields or duplicate ids."""
    model = model or Product
    try:
        entries = TypeAdapter(list[model]).validate_python(raw)
    except ValidationError as exc:
        raise CatalogError(f"Invalid {source}: {exc}") from exc
    by_id: dict = {}
    for entry in entries:
        if entry.id in by_id:
            raise CatalogError(f"Invalid {source}: duplicate id '{entry.id}'")
        by_id[entry.id] = entry
    return by_id


def _load(path: Path, model: type[BaseModel]) -> dict:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CatalogError(f"Invalid {path.name}: {exc}") from exc
    return validate_entries(raw, model, path.name)


def load_products(path: Path = PRODUCTS_PATH) -> dict[str, Product]:
    return _load(path, Product)


def load_campaigns(path: Path = CAMPAIGNS_PATH, products: dict[str, Product] | None = None) -> dict[str, Campaign]:
    campaigns = _load(path, Campaign)
    if products is not None:
        for c in campaigns.values():
            if c.product_id and c.product_id not in products:
                raise CatalogError(f"Invalid {path.name}: campaign '{c.id}' references unknown product '{c.product_id}'")
    return campaigns


PRODUCTS: dict[str, Product] = load_products()
CAMPAIGNS: dict[str, Campaign] = load_campaigns(products=PRODUCTS)


def catalog_products(category: str | None = None) -> list[Product]:
    """Products served by /api/products: everything except the legacy campaign entries."""
    return [p for p in PRODUCTS.values()
            if p.category != LEGACY_CAMPAIGN_CATEGORY and (category is None or p.category == category)]


def get_product(product_id: str) -> Product | None:
    product = PRODUCTS.get(product_id)
    return product if product and product.category != LEGACY_CAMPAIGN_CATEGORY else None


def today() -> date:
    return date.today()


def active_campaigns(on: date | None = None, campaigns: dict[str, Campaign] | None = None) -> list[Campaign]:
    """Campaigns whose end date hasn't passed (the end date itself is still active), soonest-ending first."""
    on = on or today()
    campaigns = CAMPAIGNS if campaigns is None else campaigns
    return sorted((c for c in campaigns.values() if c.end_date >= on), key=lambda c: c.end_date)
