path = r"D:\aaa111\Poetry-RAG-System\frontend\src\views\GenerateView.vue"
with open(path, "r", encoding="utf-8") as f:
    c = f.read()

# ── Block 1: onMounted session creation ─────────────────────────────────────
old1 = (
    "    const token = authStore.token\n"
    "    const res = await fetch('/api/v1/poetry/chat/session', {\n"
    "      method: 'POST',\n"
    "      headers: token ? { 'Authorization': `Bearer ${token}` } : {},\n"
    "    })\n"
    "    const data = await res.json()\n"
    "    // Backend 将 AI Service 的 session_id 包装在 data.data 里\n"
    "    sessionId.value = data?.data?.session_id || data.session_id || ''"
)
new1 = (
    "    // Spec: specs/features/interface-communication.spec.md §5\n"
    "    const newId = await apiCreateSession()\n"
    "    sessionId.value = newId"
)
if old1 in c:
    c = c.replace(old1, new1, 1)
    print("Block1 OK")
else:
    print("Block1 NOT FOUND")

# ── Block 2: streamChat fetch call ───────────────────────────────────────────
old2 = (
    "  const token = authStore.token\n"
    "  const response = await fetch('/api/v1/poetry/chat', {\n"
    "    method: 'POST',\n"
    "    headers: {\n"
    "      'Content-Type': 'application/json',\n"
    "      ...(token ? { 'Authorization': `Bearer ${token}` } : {}),\n"
    "    },\n"
    "    body: JSON.stringify({ message: text, session_id: sessionId.value }),\n"
    "  })"
)
new2 = (
    "  const token = authStore.token\n"
    "  // Spec: specs/openapi/backend.yaml §/api/v1/poetry/chat\n"
    "  const response = await fetchChatStream(text, sessionId.value, token)"
)
if old2 in c:
    c = c.replace(old2, new2, 1)
    print("Block2 OK")
else:
    print("Block2 NOT FOUND")

# ── Block 3: streamStoryboard fetch call ─────────────────────────────────────
old3 = (
    "  const token = authStore.token\n"
    "  const response = await fetch('/api/v1/poetry/storyboard', {\n"
    "    method: 'POST',\n"
    "    headers: {\n"
    "      'Content-Type': 'application/json',\n"
    "      ...(token ? { 'Authorization': `Bearer ${token}` } : {}),\n"
    "    },\n"
    "    body: JSON.stringify({ sourceText: text }),\n"
    "  })"
)
new3 = (
    "  const token = authStore.token\n"
    "  // Spec: specs/openapi/backend.yaml §/api/v1/poetry/storyboard\n"
    "  const response = await fetchStoryboardStream(text, token)"
)
if old3 in c:
    c = c.replace(old3, new3, 1)
    print("Block3 OK")
else:
    print("Block3 NOT FOUND")

with open(path, "w", encoding="utf-8", newline="") as f:
    f.write(c)
print("Saved")
