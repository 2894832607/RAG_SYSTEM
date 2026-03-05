"""快速测试 SSE 聊天接口"""
import requests
import json

r = requests.post("http://127.0.0.1:8000/ai/api/v1/chat/session", timeout=10)
print("session status:", r.status_code)
sid = r.json()["session_id"]
print("session_id:", sid)

resp = requests.post(
    "http://127.0.0.1:8000/ai/api/v1/chat",
    json={"message": "给我推荐一首关于月亮的古诗", "session_id": sid},
    stream=True,
    timeout=40,
)
print("chat status:", resp.status_code)
count = 0
for line in resp.iter_lines(decode_unicode=True):
    if line and line.startswith("data:"):
        try:
            ev = json.loads(line[5:].strip())
            t = ev.get("type", "?")
            c = ev.get("content", ev)
            print(f"[{t}] {str(c)[:100]}")
        except Exception:
            print(line[:120])
        count += 1
        if count >= 30:
            print("...(truncated)")
            break
