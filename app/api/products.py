from fastapi import APIRouter

from ..mock_data import PRODUCTS
from ..schemas import ProductsResponse

router = APIRouter(prefix="/api", tags=["products"])


@router.get("/products", response_model=ProductsResponse)
def list_products(category: str | None = None):
    # TODO(real): load data/products.json (ingested from the Raiffeisen PDF) instead of mock_data.PRODUCTS.
    products = [p for p in PRODUCTS if category is None or p.category == category]
    return ProductsResponse(products=products)
