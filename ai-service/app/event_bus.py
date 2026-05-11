"""Event Bus — Session-Scoped Event Queue Registry

提供：
- _session_event_queues : 会话事件队列注册表（session_id → asyncio.Queue）
- _current_session_id  : ContextVar，供工具线程读取当前会话 ID
- push_session_event() : 线程安全的 push 函数，供 ThreadPool 工具线程调用
- set_main_loop()      : 应用启动时注册主事件循环引用

设计说明：
    main.py 创建请求级 asyncio.Queue，注册后将 session_id 写入 ContextVar；
    generate_storyboard 等工具在 ThreadPoolExecutor 中运行，通过
    push_session_event() 使用 run_coroutine_threadsafe 安全地将事件推送
    到主事件循环的 Queue，让 SSE generator 实时消费并发送给客户端。
"""
import asyncio
import contextvars
from typing import Optional

# 全局事件队列注册表：session_id → asyncio.Queue[dict | None]
# None 值是终止哨兵，由 langgraph_producer finally 块推入
_session_event_queues: dict[str, "asyncio.Queue[dict | None]"] = {}

# ContextVar：在 /chat 协程中通过 .set() 写入 session_id；
# Python 3.7+ ThreadPoolExecutor.submit() 会自动复制调用方的 contextvars 上下文，
# 因此工具线程可以直接通过 .get() 读到正确的 session_id。
_current_session_id: contextvars.ContextVar[str] = contextvars.ContextVar(
    "_current_session_id", default=""
)

# 主事件循环引用（由 startup 事件写入，工具线程通过 run_coroutine_threadsafe 使用）
_main_event_loop: Optional[asyncio.AbstractEventLoop] = None


def set_main_loop(loop: asyncio.AbstractEventLoop) -> None:
    """应用启动时调用，记录 asyncio 主事件循环。"""
    global _main_event_loop
    _main_event_loop = loop


def push_session_event(session_id: str, event: dict) -> bool:
    """
    线程安全地向 session 队列 push 事件。

    在 ThreadPoolExecutor 工具线程中调用；使用 run_coroutine_threadsafe
    将协程调度到主事件循环执行，不阻塞工具线程。

    Args:
        session_id: 目标会话 ID
        event:      要推送的事件 dict（与 SSE data JSON 结构相同）

    Returns:
        True  — 成功提交（不等待完成）
        False — 队列未找到（会话已结束）或主循环未初始化
    """
    queue = _session_event_queues.get(session_id)
    if queue is None or _main_event_loop is None:
        return False
    asyncio.run_coroutine_threadsafe(queue.put(event), _main_event_loop)
    return True
