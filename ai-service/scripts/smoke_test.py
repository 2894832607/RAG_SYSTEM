import json
import os
import time

import requests


BASE = os.getenv("AI_BASE_URL", "http://127.0.0.1:8000")
CALLBACK_URL = os.getenv("CALLBACK_URL", f"{BASE}/ai/mock/callback")


def main() -> None:
    health = requests.get(f"{BASE}/ai/health", timeout=10)
    print("health", health.status_code, health.text)

    payload = {
        "taskId": "task-001",
        "sourceText": "明月松间照，清泉石上流",
        "callbackUrl": CALLBACK_URL,
        "callbackToken": "demo-token",
    }
    submit = requests.post(f"{BASE}/ai/api/v1/generate/async", json=payload, timeout=10)
    print("async_submit", submit.status_code, submit.text)

    time.sleep(1.5)
    if CALLBACK_URL.startswith(f"{BASE}/ai/mock/callback"):
        callback = requests.get(f"{BASE}/ai/mock/callback/task-001", timeout=10)
        print("callback", callback.status_code, callback.text)
    else:
        print("callback", "external", CALLBACK_URL)

    simple = requests.post(
        f"{BASE}/ai/api/v1/generate/simple",
        json={"sourceText": "大漠孤烟直，长河落日圆"},
        timeout=30,
    )
    print("simple", simple.status_code)
    print(simple.text)


if __name__ == "__main__":
    main()
