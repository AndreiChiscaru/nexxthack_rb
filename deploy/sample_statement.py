"""Generates a fake bank statement PDF for end-to-end testing."""
import sys

import pymupdf

ROWS = [
    ("01.09.2026", "Sold initial", "", "3.240,15"),
    ("05.09.2026", "Incasare salariu ACME SOFTWARE SRL", "+6.850,00", ""),
    ("06.09.2026", "Rata credit ipotecar BT", "-2.310,00", ""),
    ("08.09.2026", "Kaufland Romania", "-412,30", ""),
    ("10.09.2026", "Enel Energie factura", "-245,60", ""),
    ("12.09.2026", "Netflix abonament", "-59,99", ""),
    ("14.09.2026", "Superbet online", "-300,00", ""),
    ("18.09.2026", "Retragere numerar ATM", "-1.000,00", ""),
    ("20.09.2026", "Credius IFN rata", "-650,00", ""),
    ("25.09.2026", "Lidl", "-287,45", ""),
    ("28.09.2026", "Transfer primit Popescu Maria", "+500,00", ""),
    ("30.09.2026", "Comision administrare cont", "-15,00", ""),
    ("30.09.2026", "Sold final", "", "5.309,81"),
]

doc = pymupdf.open()
page = doc.new_page()
y = 60
for line in ["BANCA TRANSILVANIA - EXTRAS DE CONT", "Titular: Ion Popescu",
             "IBAN: RO49BTRL0000000000000001   Moneda: RON", "Perioada: 01.09.2026 - 30.09.2026", ""]:
    page.insert_text((40, y), line, fontsize=11)
    y += 18
for date, desc, amount, balance in ROWS:
    page.insert_text((40, y), date, fontsize=9)
    page.insert_text((110, y), desc, fontsize=9)
    page.insert_text((400, y), amount, fontsize=9)
    page.insert_text((490, y), balance, fontsize=9)
    y += 15
doc.save(sys.argv[1] if len(sys.argv) > 1 else "/tmp/extras_test.pdf")
