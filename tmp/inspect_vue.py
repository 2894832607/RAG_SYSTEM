import re

path = r"D:\aaa111\Poetry-RAG-System\frontend\src\views\GenerateView.vue"
with open(path, "r", encoding="utf-8") as f:
    c = f.read()

# Show block 1 - session creation
i = c.find("fetch('/api/v1/poetry/chat/session'")
print(f"Block1 session at: {i}")
if i >= 0:
    print(repr(c[i-60:i+400]))
print("---")

# Show block 2 - streamChat
i2 = c.find("fetch('/api/v1/poetry/chat'")
print(f"Block2 chat at: {i2}")
if i2 >= 0:
    print(repr(c[i2-50:i2+350]))
print("---")

# Show block 3 - streamStoryboard
i3 = c.find("fetch('/api/v1/poetry/storyboard'")
print(f"Block3 storyboard at: {i3}")
if i3 >= 0:
    print(repr(c[i3-50:i3+350]))
