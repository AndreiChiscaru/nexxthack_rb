import os
import sys

import anthropic
from dotenv import load_dotenv

load_dotenv("/opt/extras/.env")
client = anthropic.Anthropic()

if "--models" in sys.argv:
    for model in client.models.list(limit=50):
        print(model.id)
    sys.exit()

reply = client.messages.create(
    model=os.environ["ANTHROPIC_MODEL"],
    max_tokens=20,
    messages=[{"role": "user", "content": "Raspunde doar cu OK"}],
)
print("CLAUDE:", reply.content[0].text)
