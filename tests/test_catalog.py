"""Product catalog (data/products.json), campaigns (data/campaigns.json), their endpoints and the PDF ingest tool."""
import json
import re
from datetime import date
from types import SimpleNamespace

import pymupdf
import pytest
from fastapi.testclient import TestClient

from app import catalog
from app.agents import consultant
from app.catalog import (
    CAMPAIGNS,
    CATALOG_CATEGORIES,
    LEGACY_CAMPAIGN_CATEGORY,
    PRODUCTS,
    PRODUCTS_PATH,
    CatalogError,
    active_campaigns,
    load_campaigns,
    load_products,
)
from app.main import app
from app.sim.adapter import HOLDING_PRODUCTS
from tools import ingest_products

client = TestClient(app)


# ---------------------------------------------------------------- data files

def test_products_file_validates_with_unchanged_shape():
    raw = json.loads(PRODUCTS_PATH.read_text(encoding="utf-8"))
    assert len(raw) == len(PRODUCTS) == len(load_products())
    for entry in raw:  # the consultant's shape; as_of_date/disclaimer are optional extras
        assert {"id", "category", "name", "terms", "conditions", "best_for", "cautions"} <= set(entry)


def test_product_ids_unique():
    ids = [p["id"] for p in json.loads(PRODUCTS_PATH.read_text(encoding="utf-8"))]
    assert len(ids) == len(set(ids))


def test_every_product_has_as_of_date_and_disclaimer():
    for p in PRODUCTS.values():
        assert isinstance(p.as_of_date, date)
        assert "de la" in p.disclaimer and "nu sunt garantate" in p.disclaimer


def test_credit_rates_are_de_la_minimums():
    for p in PRODUCTS.values():
        if p.category not in ("credit", "locuinta"):
            continue
        for clause in re.findall(r"[^.;]*[Dd]obând[^.;]*\d+(?:,\d+)?\s*%[^.;]*", p.terms):
            assert "de la" in clause, f"{p.id}: rate without 'de la': {clause.strip()}"


def test_campaigns_file_validates_and_links_products():
    campaigns = load_campaigns(products=PRODUCTS)
    assert campaigns
    for c in campaigns.values():
        assert c.end_date and (c.product_id is None or c.product_id in PRODUCTS)


def _write(tmp_path, name, entries):
    path = tmp_path / name
    path.write_text(json.dumps(entries, ensure_ascii=False), encoding="utf-8")
    return path


PRODUCT = {"id": "p1", "category": "credit", "name": "P", "terms": "Dobândă de la 5%.", "conditions": "",
           "best_for": "x", "cautions": "y"}


@pytest.mark.parametrize("entries", [
    pytest.param([PRODUCT, PRODUCT], id="duplicate-id"),
    pytest.param([{k: v for k, v in PRODUCT.items() if k != "terms"}], id="missing-terms"),
    pytest.param([{**PRODUCT, "category": "criptomonede"}], id="unknown-category"),
    pytest.param([{**PRODUCT, "id": "Has Spaces"}], id="bad-id"),
])
def test_invalid_products_fail_fast(tmp_path, entries):
    with pytest.raises(CatalogError):
        load_products(_write(tmp_path, "products.json", entries))


def test_optional_fields_default_and_extra_keys_ignored(tmp_path):
    [p] = load_products(_write(tmp_path, "products.json", [{**PRODUCT, "teammate_note": "x"}])).values()
    assert p.as_of_date == catalog.CATALOG_AS_OF and p.disclaimer == catalog.DEFAULT_DISCLAIMER
    [p] = load_products(_write(tmp_path, "products.json", [{**PRODUCT, "as_of_date": "2026-11-15"}])).values()
    assert p.as_of_date == date(2026, 11, 15)


@pytest.mark.parametrize("entry", [
    pytest.param({"id": "c", "name": "C", "terms": "t", "conditions": "", "best_for": "", "cautions": ""}, id="no-end-date"),
    pytest.param({"id": "c", "name": "C", "terms": "t", "conditions": "", "best_for": "", "cautions": "",
                  "start_date": "2026-12-01", "end_date": "2026-11-01"}, id="ends-before-start"),
    pytest.param({"id": "c", "name": "C", "terms": "t", "conditions": "", "best_for": "", "cautions": "",
                  "end_date": "2026-12-01", "product_id": "nu_exista"}, id="unknown-product"),
])
def test_invalid_campaigns_fail_fast(tmp_path, entry):
    with pytest.raises(CatalogError):
        load_campaigns(_write(tmp_path, "campaigns.json", [entry]), products=PRODUCTS)


# ---------------------------------------------------------------- endpoints

def test_products_endpoint_serves_catalog_without_campaigns():
    body = client.get("/api/products").json()["products"]
    assert {p["id"] for p in body} == {i for i, p in PRODUCTS.items() if p.category != LEGACY_CAMPAIGN_CATEGORY}
    assert all(p["as_of_date"] == "2026-10-28" for p in body)


@pytest.mark.parametrize("category", CATALOG_CATEGORIES)
def test_each_category_filter(category):
    body = client.get("/api/products", params={"category": category}).json()["products"]
    assert body and all(p["category"] == category for p in body)
    assert {p["id"] for p in body} == {i for i, p in PRODUCTS.items() if p.category == category}


def test_unknown_category_and_campaign_category_are_400():
    assert client.get("/api/products", params={"category": "criptomonede"}).status_code == 400
    r = client.get("/api/products", params={"category": "campanie"})
    assert r.status_code == 400 and "/api/campaigns" in r.json()["detail"]


def test_product_by_id():
    r = client.get("/api/products/credit_nevoi")
    assert r.status_code == 200
    assert r.json()["name"] == "Credit de nevoi personale" and r.json()["disclaimer"]
    assert client.get("/api/products/nu_exista").status_code == 404
    assert client.get("/api/products/campanie_debit").status_code == 404  # campaigns aren't catalog products


def test_campaigns_endpoint_hides_expired(monkeypatch):
    monkeypatch.setattr(catalog, "today", lambda: date(2026, 11, 3))  # campanie_credit ended 2026-11-02
    ids = [c["id"] for c in client.get("/api/campaigns").json()["campaigns"]]
    assert "campanie_credit" not in ids and "campanie_debit" in ids
    monkeypatch.setattr(catalog, "today", lambda: date(2026, 11, 2))  # last day still active
    ids = [c["id"] for c in client.get("/api/campaigns").json()["campaigns"]]
    assert ids[0] == "campanie_credit"  # soonest-ending first
    monkeypatch.setattr(catalog, "today", lambda: date(2027, 2, 1))
    assert client.get("/api/campaigns").json()["campaigns"] == []


def test_active_campaigns_on_date():
    assert {c.id for c in active_campaigns(date(2026, 12, 31))} == {"campanie_debit", "campanie_premium"}
    assert active_campaigns(date(2027, 1, 1)) == [CAMPAIGNS["campanie_debit"]]


# ---------------------------------------------------------------- references to the catalog

def test_consultant_reads_the_same_catalog():
    assert {p["id"] for p in consultant.PRODUCTS} == set(PRODUCTS)
    assert set(consultant.CATEGORIES) == {p.category for p in PRODUCTS.values()}


def test_every_product_id_the_backend_references_exists():
    referenced = set(HOLDING_PRODUCTS.values()) | {c.product_id for c in CAMPAIGNS.values() if c.product_id}
    assert referenced <= set(PRODUCTS), referenced - set(PRODUCTS)
    sid = client.post("/api/session").json()["session_id"]
    calls = client.post("/api/advisor/message", json={"session_id": sid, "text": "Vreau un credit"}).json()["tool_calls"]
    compared = [c for c in calls if c["name"] == "compare_products"]
    assert compared and set(compared[0]["args"]["ids"]) <= set(PRODUCTS)


def test_game_state_products_use_catalog_ids():
    sid = client.post("/api/session").json()["session_id"]
    state = client.post("/api/game/start", json={"session_id": sid}).json()["state"]
    assert state["products"] and all(h["id"] in PRODUCTS for h in state["products"])


# ---------------------------------------------------------------- ingest tool (no network: fake client)

class FakeStream:
    def __init__(self, text, stop_reason="end_turn"):
        self.message = SimpleNamespace(stop_reason=stop_reason, content=[SimpleNamespace(type="text", text=text)])

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def get_final_message(self):
        return self.message


def fake_client(products, stop_reason="end_turn"):
    stream = lambda **kwargs: FakeStream(json.dumps({"products": products}), stop_reason)  # noqa: E731
    return SimpleNamespace(beta=SimpleNamespace(messages=SimpleNamespace(stream=stream)))


def _offer_pdf(tmp_path):
    doc = pymupdf.open()
    doc.new_page().insert_text((40, 60), "Raiffeisen Bank - oferta credite: Credit de nevoi personale, dobanda de la 5,95%.")
    path = tmp_path / "oferta.pdf"
    doc.save(path)
    return path


PDF_PRODUCTS = [
    {**PRODUCT, "id": "credit_nevoi", "name": "Credit de nevoi personale", "terms": "Dobândă fixă de la 5,49%."},
    {**PRODUCT, "id": "credit_nou", "name": "Credit nou"},
]


def test_ingest_dry_run_writes_nothing(tmp_path, capsys):
    out = tmp_path / "out.json"
    assert ingest_products.main([str(_offer_pdf(tmp_path)), "--out", str(out), "--dry-run"],
                                client=fake_client(PDF_PRODUCTS)) == 0
    assert not out.exists()
    captured = capsys.readouterr()
    assert json.loads(captured.out)[0]["id"] == "credit_nevoi"
    report = json.loads(captured.err)["review"]
    assert report["added"] == ["credit_nou"] and report["changed"] == ["credit_nevoi"]
    assert "pilon3" in report["missing_from_pdf"]


def test_ingest_writes_review_file_validated_with_dates(tmp_path):
    out = tmp_path / "products.from_pdf.json"
    assert ingest_products.main([str(_offer_pdf(tmp_path)), "--out", str(out), "--as-of", "2026-11-01"],
                                client=fake_client(PDF_PRODUCTS)) == 0
    written = json.loads(out.read_text(encoding="utf-8"))
    assert [p["as_of_date"] for p in written] == ["2026-11-01", "2026-11-01"]
    assert load_products(out)  # same validation as the app's startup


def test_ingest_never_overwrites_products_json(tmp_path):
    before = PRODUCTS_PATH.read_bytes()
    assert ingest_products.main([str(_offer_pdf(tmp_path)), "--out", str(PRODUCTS_PATH)],
                                client=fake_client(PDF_PRODUCTS)) == 1
    assert PRODUCTS_PATH.read_bytes() == before


def test_ingest_rejects_invalid_model_output(tmp_path):
    bad = [{**PRODUCT, "category": "criptomonede"}]
    assert ingest_products.main([str(_offer_pdf(tmp_path)), "--dry-run"], client=fake_client(bad)) == 1


def test_ingest_stops_on_truncated_output(tmp_path):
    assert ingest_products.main([str(_offer_pdf(tmp_path)), "--dry-run"],
                                client=fake_client(PDF_PRODUCTS, stop_reason="max_tokens")) == 1
