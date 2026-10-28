"""Downloads the consolidated texts of the laws used by the accountant agent from legislatie.just.ro and splits them
into article chunks for retrieval. Writes data/legislatie/index.json. Usage: build_legal_index.py [html_cache_dir]"""
import json
import re
import sys
import urllib.request
from datetime import date
from html import unescape
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "legislatie" / "index.json"
LAWS = [
    {"id": "codul_fiscal", "name": "Codul fiscal (Legea 227/2015)", "doc": 171282},
    {"id": "procedura_fiscala", "name": "Codul de procedură fiscală (Legea 207/2015)", "doc": 309359},
    {"id": "registrul_comertului", "name": "Legea 265/2022 privind registrul comerțului", "doc": 257835},
]
URL = "https://legislatie.just.ro/Public/DetaliiDocument/{doc}"
CHUNK_CHARS = 1800
BREAK_CLASSES = {"S_ALN", "S_LIT", "S_PCT", "S_LIN", "S_PAR"}
HEADING_LEVELS = {"S_TTL": 0, "S_CAP": 1, "S_SEC": 2}


class LawParser(HTMLParser):
    """Walks the legislatie.just.ro markup: S_TTL/S_CAP/S_SEC headings, S_ART articles, S_NTA amendment notes (skipped)."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack: list[str | None] = []
        self.articles: list[dict] = []
        self.headings = ["", "", ""]
        self.heading_buf: dict[int, list[str]] = {}
        self.article: dict | None = None

    def _classes(self):
        return [c for c in self.stack if c]

    def handle_starttag(self, tag, attrs):
        if tag in ("br", "img", "input", "meta", "link", "hr"):
            if tag == "br" and self.article is not None:
                self.article["parts"].append("\n")
            return
        cls = dict(attrs).get("class")
        cls = cls.split()[0] if cls else None
        self.stack.append(cls)
        if cls == "S_ART":
            self._close_article()
            self.article = {"title": "", "name": "", "parts": [], "headings": [h for h in self.headings if h]}
        elif cls in BREAK_CLASSES and self.article is not None:
            self.article["parts"].append("\n")
        elif cls and cls.endswith(("_TTL", "_DEN")) and cls[:5] in HEADING_LEVELS:
            level = HEADING_LEVELS[cls[:5]]
            if cls.endswith("_TTL"):
                self.heading_buf = {level: []}
                for deeper in range(level, 3):
                    self.headings[deeper] = ""
            self.heading_buf.setdefault(level, [])

    def handle_endtag(self, tag):
        if tag in ("br", "img", "input", "meta", "link", "hr"):
            return
        if self.stack:
            cls = self.stack.pop()
            if cls and cls[:5] in HEADING_LEVELS and cls.endswith("_DEN"):
                level = HEADING_LEVELS[cls[:5]]
                text = " ".join("".join(self.heading_buf.get(level, [])).split())
                if text:
                    self.headings[level] = text

    def handle_data(self, data):
        classes = self._classes()
        if any(c.startswith("S_NTA") for c in classes):
            return
        if classes and classes[-1][:5] in HEADING_LEVELS and classes[-1].endswith(("_TTL", "_DEN")):
            level = HEADING_LEVELS[classes[-1][:5]]
            self.heading_buf.setdefault(level, []).append(data + " ")
            if classes[-1].endswith("_TTL"):
                return
        if self.article is None:
            return
        if "S_ART_TTL" in classes:
            self.article["title"] += data
        elif "S_ART_DEN" in classes:
            self.article["name"] += data
        elif any(c.startswith("S_ART") or c.startswith(("S_ALN", "S_LIT", "S_PCT", "S_LIN", "S_PAR", "S_LGI")) for c in classes):
            self.article["parts"].append(data)

    def _close_article(self):
        if self.article is not None:
            self.articles.append(self.article)
        self.article = None

    def close(self):
        super().close()
        self._close_article()


def clean(text: str) -> str:
    text = unescape(text).replace("\xa0", " ")
    lines = [" ".join(line.split()).removeprefix("+ ").removeprefix("+") for line in text.split("\n")]
    return "\n".join(line for line in lines if line)


def chunks(text: str):
    current = ""
    for para in text.split("\n"):
        if current and len(current) + len(para) > CHUNK_CHARS:
            yield current
            current = ""
        while len(para) > CHUNK_CHARS:
            yield para[:CHUNK_CHARS]
            para = para[CHUNK_CHARS:]
        current = f"{current}\n{para}" if current else para
    if current:
        yield current


def fetch(doc: int, cache: Path | None) -> str:
    cached = cache / f"{doc}.html" if cache else None
    if cached and cached.exists():
        return cached.read_text(encoding="utf-8", errors="replace")
    req = urllib.request.Request(URL.format(doc=doc), headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=180) as r:
        html = r.read().decode("utf-8", errors="replace")
    if cached:
        cached.write_text(html, encoding="utf-8")
    return html


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    cache = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    if cache:
        cache.mkdir(parents=True, exist_ok=True)
    records = []
    for law in LAWS:
        parser = LawParser()
        parser.feed(fetch(law["doc"], cache))
        parser.close()
        count = 0
        for art in parser.articles:
            title = " ".join(art["title"].split())
            match = re.search(r"Articolul\s+(\S+)", title)
            if not match:
                continue
            number = match.group(1)
            body = clean("".join(art["parts"]))
            if len(body) < 20:
                continue
            name = " ".join(art["name"].split())
            parts = list(chunks(body))
            for i, part in enumerate(parts):
                records.append({
                    "law": law["id"], "source": law["name"], "article": number, "name": name,
                    "context": " › ".join(art["headings"]), "part": f"{i + 1}/{len(parts)}" if len(parts) > 1 else "",
                    "text": part, "url": URL.format(doc=law["doc"]),
                })
            count += 1
        print(f"{law['name']}: {count} articole")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"built": date.today().isoformat(), "chunks": records}, ensure_ascii=False), encoding="utf-8")
    print(f"{len(records)} fragmente -> {OUT} ({OUT.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
