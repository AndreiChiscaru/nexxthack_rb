"""Checks shared memory, streaming, the ONRC dossier review and an expense invoice through the HTTP API.
Usage: demo_features_test.py <onrc.pdf> <fiscal.pdf> <invoice> [base_url]"""
import codecs
import json
import sys
import time
import urllib.error
import urllib.request
import uuid

ONRC, FISCAL, INVOICE = sys.argv[1:4]
BASE = (sys.argv[4] if len(sys.argv) > 4 else "http://127.0.0.1:8000").rstrip("/") + "/api/demo"


def raw(method, path, payload=None, files=None):
    headers, body = {}, None
    if payload is not None:
        headers["Content-Type"] = "application/json"
        body = json.dumps(payload).encode()
    elif files:
        boundary = uuid.uuid4().hex
        parts = []
        for name, (filename, content, ctype) in files.items():
            parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"; filename="{filename}"\r\n'
                         f"Content-Type: {ctype}\r\n\r\n".encode() + content + b"\r\n")
        body = b"".join(parts) + f"--{boundary}--\r\n".encode()
        headers["Content-Type"] = f"multipart/form-data; boundary={boundary}"
    req = urllib.request.Request(BASE + path, data=body, method=method, headers=headers)
    try:
        return urllib.request.urlopen(req, timeout=300)
    except urllib.error.HTTPError as exc:
        raise SystemExit(f"HTTP {exc.code} {path}: {exc.read()[:300].decode()}")


def sse(method, path, **kw):
    started = time.time()
    first = None
    events, view = [], None
    decoder = codecs.getincrementaldecoder("utf-8")()
    with raw(method, path, **kw) as r:
        buf = ""
        while True:
            data = r.read(256)
            buf += decoder.decode(data, final=not data)
            while "\n\n" in buf:
                block, buf = buf.split("\n\n", 1)
                block = block.strip()
                if not block.startswith("data:"):
                    continue
                ev = json.loads(block[5:])
                if first is None and ev["type"] in ("text", "status", "tool_start"):
                    first = time.time() - started
                if ev["type"] == "error":
                    raise SystemExit("EROARE agent: " + ev["message"])
                if ev["type"] == "view":
                    view = ev["view"]
                else:
                    events.append(ev)
            if not data:
                break
    return events, view, first or -1, time.time() - started


def show(title, events, view, elapsed_first, elapsed):
    text = "".join(e.get("delta", "") for e in events if e["type"] == "text")
    deltas = sum(1 for e in events if e["type"] == "text")
    print(f"\n== {title} ==  primul token la {elapsed_first:.1f}s / total {elapsed:.1f}s, {deltas} fragmente de text")
    print(text[:800])
    for e in events:
        if e["type"] == "tool_end":
            print("   tool:", f"{e['name']} -> {e['summary']}"[:200])
    print("   fișă:", " | ".join(n["text"][:75] for n in view["memory"][-4:]) or "(goală)")
    return text


with raw("POST", "/session") as r:
    sid = json.load(r)["session_id"]
print("sesiune", sid)

events, view, t1, t2 = sse("POST", f"/business/{sid}/message", payload={
    "text": "Vreau să-mi deschid un SRL de design grafic, Atelier Verde, și estimez 5.000 lei venit pe lună. Ține minte, te rog."})
biz = show("contabilul notează intenția", events, view, t1, t2)

events, view, t1, t2 = sse("POST", f"/consultant/{sid}/message", payload={
    "text": "Ce știi deja despre planurile mele de afacere? Nu ți-am spus eu ție nimic."})
cons = show("consultantul citește fișa", events, view, t1, t2)
mentioned = "verde" in cons.lower() or "design" in cons.lower() or "srl" in cons.lower() or "5.000" in cons or "5000" in cons
print("   consultantul știe de la contabil:", "DA" if mentioned else "NU")

for path, name in ((ONRC, "cerere_onrc.pdf"), (FISCAL, "cerere_fiscala.pdf"), (INVOICE, "factura.txt")):
    events, view, t1, t2 = sse("POST", f"/business/{sid}/document",
                               files={"file": (name, open(path, "rb").read(), "application/octet-stream")})
    show("document " + name, events, view, t1, t2)

events, view, t1, t2 = sse("POST", f"/business/{sid}/message", payload={
    "text": "Verifică dosarul meu de SRL pentru ONRC: ce am încărcat și ce lipsește? Apoi spune-mi, pentru factura încărcată, "
            "ce e deductibil și în ce procent, la regimul de impozit pe profit."})
show("dosar + deductibilitate", events, view, t1, t2)
