from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..catalog import (
    CATALOG_CATEGORIES,
    LEGACY_CAMPAIGN_CATEGORY,
    Campaign,
    Product,
    active_campaigns,
    catalog_products,
    get_product,
)

router = APIRouter(prefix="/api", tags=["products"])


class ProductsResponse(BaseModel):
    products: list[Product]


class CampaignsResponse(BaseModel):
    campaigns: list[Campaign]


@router.get("/products", response_model=ProductsResponse)
def list_products(category: str | None = None):
    if category == LEGACY_CAMPAIGN_CATEGORY:
        raise HTTPException(400, "Campaniile sunt la GET /api/campaigns.")
    if category is not None and category not in CATALOG_CATEGORIES:
        raise HTTPException(400, f"Categorie necunoscută: {category}. Alege din {list(CATALOG_CATEGORIES)}.")
    return ProductsResponse(products=catalog_products(category))


@router.get("/products/{product_id}", response_model=Product)
def product(product_id: str):
    found = get_product(product_id)
    if found is None:
        raise HTTPException(404, f"Produs necunoscut: {product_id}.")
    return found


@router.get("/campaigns", response_model=CampaignsResponse)
def campaigns():
    return CampaignsResponse(campaigns=active_campaigns())
