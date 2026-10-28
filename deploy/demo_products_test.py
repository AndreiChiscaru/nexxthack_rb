"""Asks the consultant one question and prints the answer. Usage: demo_products_test.py [base_url]"""
import codecs
import json
import sys
import urllib.request

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000").rstrip("/") + "/api/demo"
QUESTION = ("Am 26 de ani, câștig 6.500 lei net și vreau avansul pentru un apartament. "
            "Am 8.000 lei care stau în contul curent și un fond de urgență aproape inexistent. "
            "Ce produse Raiffeisen mi se potrivesc pentru economii și, mai târziu, pentru locuință?")


def post(path, payload):
    req = urllib.request.Request(BASE + path, data=json.dumps(payload).encode(), method="POST",
                                 headers={"Content-Type": "application/json"})
    return urllib.request.urlopen(req, timeout=180)


decoder = codecs.getincrementaldecoder("utf-8")()
with post("/session", {}) as r:
    sid = json.load(r)["session_id"]
buf, text, tools = "", [], []
with post(f"/consultant/{sid}/message", {"text": QUESTION}) as r:
    while True:
        data = r.read(512)
        buf += decoder.decode(data, final=not data)
        while "\n\n" in buf:
            block, buf = buf.split("\n\n", 1)
            block = block.strip()
            if not block.startswith("data:"):
                continue
            ev = json.loads(block[5:])
            if ev["type"] == "error":
                raise SystemExit(ev["message"])
            if ev["type"] == "text":
                text.append(ev["delta"])
            if ev["type"] == "tool_end" and ev["name"] == "search_products":
                tools.append(ev["summary"])
        if not data:
            break
print("PRODUSE CĂUTATE:", " ; ".join(tools))
print("\n" + "".join(text))
