import json
import requests

url = "http://127.0.0.1:8000/ai/api/v1/chat"
payload = {
    "message": "请先思考再回答：春江花月夜的核心意境是什么？",
    "session_id": "doubao-chat-test"
}

thinking = 0
token = 0
seen = 0

with requests.post(url, json=payload, stream=True, timeout=120) as r:
    print("status=", r.status_code)
    r.raise_for_status()
    for raw in r.iter_lines(decode_unicode=True):
        if not raw:
            continue
        line = raw.strip()
        if not line.startswith("data:"):
            continue
        data = line[5:].strip()
        if data == "[DONE]":
            break
        try:
            evt = json.loads(data)
        except json.JSONDecodeError:
            continue

        seen += 1
        t = evt.get("type")
        if t == "thinking":
            thinking += 1
            if thinking <= 6:
                print("thinking:", repr((evt.get("content") or "")[:60]))
        elif t == "token":
            token += 1

        if seen >= 120:
            break

print("events=", seen, "thinking=", thinking, "token=", token)
