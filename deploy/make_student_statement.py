#!/usr/bin/env python3
"""Fictional 12-month statement for a student with irresponsible habits.

Matei Pop, 21, lives with his parents in Iași, works part-time at a café.
He spends heavily on Uber and restaurants, bets, buys on PayPo and withdraws cash.
Every name, IBAN and amount is invented. Run on a machine with PyMuPDF.
"""
import random
import calendar
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT_PDF = ROOT / "static" / "samples" / "extras_student.pdf"
OUT_TXT = ROOT / "data" / "extras_student.txt"
OUT_COPY = ROOT / "documente_test_agenti" / "FICTIV_extras_student_12_luni.pdf"

random.seed(20261028)


def money(value: float) -> str:
    sign = "+" if value > 0 else "-"
    whole, cents = f"{abs(value):.2f}".split(".")
    groups = []
    while whole:
        groups.append(whole[-3:])
        whole = whole[:-3]
    return f"{sign}{'.'.join(reversed(groups))},{cents}"


def month_rows(year: int, month: int) -> list[tuple[str, float]]:
    last = calendar.monthrange(year, month)[1]
    rows: list[tuple[date, str, float]] = []

    def add(day: int, desc: str, amount: float):
        rows.append((date(year, month, min(day, last)), desc, round(amount, 2)))

    add(1, "Transfer primit Ionescu Elena", 1000 if month == 12 else 400)
    add(5, "Incasare salariu Cafea de Cartier SRL", random.choice((1700, 1800, 1900, 2000, 2100, 1600)))
    add(3, "Orange my account", -29)
    add(6, "Netflix.com", -39.99)
    add(6, "Spotify AB", -24.99)
    add(7, "HBO Max", -29.99)
    add(8, "World Class Iasi", -149)

    for _ in range(random.randint(10, 13)):
        add(random.randint(1, last), random.choice(("Uber Trip", "Bolt")), -random.choice((32, 38, 45, 58, 72, 86)))
    for name, low, high, times in (("Restaurant Spoon", 75, 140, (1, 2)), ("Beraria Veche", 90, 160, (1, 2)),
                                   ("Pizza Napoli", 48, 85, (1, 2)), ("McDonald's Palas", 32, 58, (1, 2))):
        for _ in range(random.randint(*times)):
            add(random.randint(1, last), name, -random.randint(low, high))
    for _ in range(random.randint(3, 5)):
        add(random.randint(1, last), "Glovo", -random.randint(36, 64))
    for _ in range(random.randint(6, 9)):
        add(random.randint(1, last), "5 to go", -random.choice((12, 14, 16)))
    if random.random() < 0.65:
        add(random.randint(2, 20), "Kaufland Iasi", -random.randint(35, 75))
    if random.random() < 0.8:
        add(random.randint(1, last), random.choice(("About You", "H&M Iasi", "Bershka")), -random.randint(129, 289))
    for _ in range(random.randint(2, 4)):
        add(random.randint(1, last), "Superbet", -random.choice((40, 50, 80, 100)))
    add(random.randint(10, 24), "Retragere numerar ATM", -random.choice((100, 150, 200, 250)))
    add(12, "PayPo rata", -random.choice((89, 119)))
    # Faculty scholarship, paid every month of the statement. Fixed so the monthly average stays 800.
    add(10, "Bursa facultate UAIC Iasi", 800)
    rows.sort(key=lambda r: (r[0], r[1]))
    return [(d.strftime("%d.%m.%Y"), desc, amount) for d, desc, amount in rows]


def build() -> tuple[str, float]:
    lines = [
        "DOCUMENT FICTIV - generat pentru demo, nu este un extras real",
        "Raiffeisen Bank - Extras de cont",
        "Titular: MATEI POP",
        "Varsta: 21",
        "Ocupatie: Student, part-time la cafenea",
        "Locuinta: cu parintii",
        "Cont curent: RO49RZBR0000060012345678",
        "Perioada: 01.11.2025 - 31.10.2026",
        "Moneda: RON",
        "",
        "Data        Descriere                                      Suma",
    ]
    balance = 1450.0
    lines.append(f"01.11.2025  {'Sold initial':<46} {money(balance):>12}")
    total_out = 0.0
    for year, month in [(2025, 11), (2025, 12)] + [(2026, m) for m in range(1, 11)]:
        for stamp, desc, amount in month_rows(year, month):
            balance = round(balance + amount, 2)
            if amount < 0:
                total_out += -amount
            lines.append(f"{stamp}  {desc:<46} {money(amount):>12}")
    lines.append("")
    lines.append(f"31.10.2026  Sold final                                 {money(balance):>12}")
    return "\n".join(lines) + "\n", balance


def to_pdf(text: str, path: Path):
    import pymupdf as fitz

    doc = fitz.open()
    rows = text.splitlines()
    per_page = 46
    for start in range(0, len(rows), per_page):
        page = doc.new_page(width=595, height=842)
        if start == 0:
            page.insert_textbox(fitz.Rect(40, 28, 555, 52), "DOCUMENT FICTIV",
                                 fontsize=14, fontname="hebo", color=(0.7, 0.1, 0.1), align=1)
        y = 64
        for line in rows[start:start + per_page]:
            page.insert_text((36, y), line[:110], fontsize=8, fontname="cour")
            y += 16
    path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(path)
    doc.close()
    OUT_COPY.parent.mkdir(parents=True, exist_ok=True)
    OUT_COPY.write_bytes(path.read_bytes())


def main():
    text, balance = build()
    OUT_TXT.parent.mkdir(parents=True, exist_ok=True)
    OUT_TXT.write_text(text, encoding="utf-8")
    to_pdf(text, OUT_PDF)
    print(f"scris {OUT_TXT.name} si {OUT_PDF.relative_to(ROOT)}")
    print(f"sold final {balance:.2f}, linii {text.count(chr(10))}")


if __name__ == "__main__":
    main()
