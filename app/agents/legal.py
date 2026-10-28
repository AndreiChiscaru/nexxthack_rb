"""Retrieval over the consolidated Romanian laws (built by deploy/build_legal_index.py): BM25 with light stemming."""
import json
import math
import re
import unicodedata
from collections import Counter
from functools import lru_cache
from pathlib import Path

INDEX = Path(__file__).resolve().parents[2] / "data" / "legislatie" / "index.json"
LAWS = {"codul_fiscal": "Codul fiscal", "procedura_fiscala": "Codul de procedură fiscală",
        "registrul_comertului": "Legea 265/2022 (registrul comerțului)"}
STOP = set("""a ai al ale alte am ar are as au ca care cat ce cea cei cel cele cu cum da dar daca de decat din dintre
după dupa e ea ei el este fi fie fost iar il in inca intr intre la le li lor lui mai ma mi ne nici nu o or ori pe pentru
prin sa sau se si sunt sub te tot toti un una unei unor unui va vor""".split())
K1, B = 1.4, 0.75


def _fold(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.lower())
    return "".join(c for c in text if not unicodedata.combining(c))


def tokens(text: str) -> list[str]:
    return [w[:7] for w in re.findall(r"[a-z0-9]+", _fold(text)) if w not in STOP and (len(w) > 1 or w.isdigit())]


@lru_cache(maxsize=1)
def _index():
    if not INDEX.exists():
        return None
    data = json.loads(INDEX.read_text(encoding="utf-8"))
    docs = data["chunks"]
    tfs, df = [], Counter()
    for doc in docs:
        tf = Counter(tokens(f"{doc['name']} {doc['name']} {doc['context']} {doc['text']}"))
        tfs.append(tf)
        df.update(tf.keys())
    lengths = [sum(tf.values()) for tf in tfs]
    avg = sum(lengths) / max(len(lengths), 1)
    idf = {t: math.log(1 + (len(docs) - n + 0.5) / (n + 0.5)) for t, n in df.items()}
    return {"built": data["built"], "docs": docs, "tfs": tfs, "lengths": lengths, "avg": avg, "idf": idf}


def available() -> bool:
    return _index() is not None


def search(query: str, law: str | None = None, article: str | None = None, k: int = 5) -> dict:
    index = _index()
    if not index:
        return {"error": "Indexul de legislație nu este construit (rulează deploy/build_legal_index.py)."}
    q = Counter(tokens(query))
    scored = []
    for i, doc in enumerate(index["docs"]):
        if law and doc["law"] != law:
            continue
        if article and doc["article"].lower() != str(article).lower():
            continue
        tf, length = index["tfs"][i], index["lengths"][i]
        score = 0.0
        for term, qn in q.items():
            n = tf.get(term)
            if n:
                score += index["idf"][term] * n * (K1 + 1) / (n + K1 * (1 - B + B * length / index["avg"])) * qn
        if article and not q:
            score = 1.0
        if score > 0:
            scored.append((score, i))
    scored.sort(reverse=True)
    results = []
    for score, i in scored[:k]:
        doc = index["docs"][i]
        results.append({
            "sursa": doc["source"], "articol": f"Art. {doc['article']}" + (f" (fragment {doc['part']})" if doc["part"] else ""),
            "denumire": doc["name"], "context": doc["context"], "text": doc["text"][:1500], "url": doc["url"],
            "relevanta": round(score, 2),
        })
    cites = ", ".join(f"{LAWS.get(index['docs'][i]['law'], '')} art. {index['docs'][i]['article']}" for _, i in scored[:k])
    return {"rezultate": results, "forma_consolidata_la": index["built"],
            "nota": "Text oficial consolidat de pe legislatie.just.ro; citează articolul folosit.",
            "summary": f"{len(results)} fragmente: {cites}" if results else "Niciun fragment relevant găsit."}
