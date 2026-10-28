"""End-to-end check of the 4 agents through the HTTP API (uses Claude). Usage: demo_e2e.py [base_url] [statement.pdf]"""
import json
import sys
import time
import urllib.error
import urllib.request
import uuid

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000").rstrip("/") + "/api/demo"
STATEMENT = sys.argv[2] if len(sys.argv) > 2 else None


def _request(method, url, json=None, files=None, data=None):
    headers, body = {}, None
    if json is not None:
        headers["Content-Type"] = "application/json"
        body = _json.dumps(json).encode()
    elif files:
        boundary = uuid.uuid4().hex
        parts = []
        for name, value in (data or {}).items():
            parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'.encode())
        for name, (filename, content, ctype) in files.items():
            content = content.read() if hasattr(content, "read") else content
            parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"; filename="{filename}"\r\n'
                         f"Content-Type: {ctype}\r\n\r\n".encode() + content + b"\r\n")
        body = b"".join(parts) + f"--{boundary}--\r\n".encode()
        headers["Content-Type"] = f"multipart/form-data; boundary={boundary}"
    req = urllib.request.Request(url, data=body, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=300) as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


_json = json


def show(view, part):
    chat = view["onboarding"]["chat"] if part == "onboarding" else view[part]
    last = chat[-1]
    tools = "; ".join(f"{t['name']} -> {t['summary']}" for t in last.get("tool_calls") or [])
    print(f"\n[{part}] {last['text'][:700]}")
    if tools:
        print(f"   tools: {tools}")


def call(method, path, **kw):
    t = time.time()
    status, text = _request(method, BASE + path, **kw)
    if status >= 400:
        print("HTTP", status, text[:500])
        sys.exit(1)
    print(f"   ({time.time() - t:.1f}s)")
    return _json.loads(text)


view = call("POST", "/session")
sid = view["session_id"]
print("sesiune", sid)

if STATEMENT:
    with open(STATEMENT, "rb") as f:
        view = call("POST", f"/onboarding/{sid}/statement", files={"file": (STATEMENT.rsplit("/", 1)[-1], f, "application/pdf")})
    show(view, "onboarding")

answers = [
    "Salut, sunt Maria, am 26 de ani și lucrez ca designer. Aș vrea să strâng avansul pentru un apartament, cam 50.000 lei în 3 ani.",
    "Câștig 6500 lei net pe lună. Chiria e 1800, utilitățile vreo 400 și am abonamente de 90 lei.",
    "La mâncare dau cam 1200, transport 200, ieșiri 500. În cont am 2500 lei și economii 6000. Nu am credite.",
    "Dacă investiția ar scădea 10% aș aștepta să își revină.",
    "Da, e corect, putem începe.",
]
for text in answers:
    if view["onboarding"]["done"]:
        break
    print("\n> user:", text)
    view = call("POST", f"/onboarding/{sid}/message", json={"text": text})
    show(view, "onboarding")
print("\nlipsesc:", view["profile"]["missing"], "| done:", view["onboarding"]["done"], "| scenariu:", view["onboarding"]["scenario"])

view = call("POST", f"/game/{sid}/start")
for _ in range(3):
    if view["game"]["pending_event"]:
        break
    view = call("POST", f"/game/{sid}/advance")
ev = view["game"]["pending_event"]
print("\neveniment:", ev and ev["title"])

view = call("POST", f"/consultant/{sid}/message", json={"text": "Ce opțiune aleg la evenimentul ăsta și sunt pe drumul cel bun spre scop?"})
show(view, "consultant")

view = call("POST", f"/business/{sid}/message", json={"text": "Vreau să fac design pe cont propriu: estimez 5000 lei/lună venit și 600 lei/lună cheltuieli. PFA sau SRL?"})
show(view, "business")

doc = ("FACTURA nr. 0012 / 15.10.2026\nFurnizor: Maria Design PFA, CUI 51234567\nClient: Alfa Soft SRL, CUI RO12345678\n"
       "Servicii design identitate vizuala: 4.500,00 lei\nTVA: neplatitor de TVA (art. 310 Cod fiscal)\nTotal de plata: 4.500,00 lei\n"
       "Termen de plata: 30 zile\nPlata prin transfer bancar in contul RO49RZBR0000060012345678").encode()
view = call("POST", f"/business/{sid}/document", files={"file": ("factura.txt", doc, "text/plain")}, data={"note": ""})
show(view, "business")

view = call("POST", f"/business/{sid}/message", json={"text": "Ok, pornește afacerea în joc ca PFA, cost inițial 1000 lei, cu cifrele de mai sus."})
show(view, "business")
print("\nafacere în joc:", view["game"]["business"])
