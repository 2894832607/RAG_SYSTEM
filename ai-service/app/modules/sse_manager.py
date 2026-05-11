"""
SSE Event Manager - 管理 Server-Sent Events 订阅和广播

功能：
1. 维护活跃的 SSE 订阅者队列
2. 支持按 task_id 广播事件
3. 自动清理断开的连接
"""
import asyncio
import logging
from collections import defaultdict
from datetime import datetime
from typing import Dict, Set, Callable
from app.schemas.requests import ProgressEvent

logger = logging.getLogger(__name__)


class SSEEventManager:
    """SSE 事件管理器 - 单例模式"""
    
    def __init__(self):
        # task_id -> Set[queue] 每个任务有多个订阅者（前端可能多标签页）
        self._queues: Dict[str, Set[asyncio.Queue]] = defaultdict(set)
        # 跟踪所有活跃的连接
        self._active_connections: Set[str] = set()  # task_ids
    
    def subscribe(self, task_id: str) -> asyncio.Queue:
        """
        订阅某个任务的进度事件
        
        Args:
            task_id: 任务 ID
            
        Returns:
            asyncio.Queue: 用于接收事件的队列
        """
        queue: asyncio.Queue = asyncio.Queue()
        self._queues[task_id].add(queue)
        self._active_connections.add(task_id)
        logger.info(f"[SSE] 新订阅：task_id={task_id}, 当前订阅数={len(self._queues[task_id])}")
        return queue
    
    def unsubscribe(self, task_id: str, queue: asyncio.Queue) -> None:
        """取消订阅"""
        if task_id in self._queues and queue in self._queues[task_id]:
            self._queues[task_id].discard(queue)
            logger.debug(f"[SSE] 取消订阅：task_id={task_id}, 剩余订阅数={len(self._queues[task_id])}")
            
            # 如果没有订阅者了，清理任务记录
            if not self._queues[task_id]:
                del self._queues[task_id]
                self._active_connections.discard(task_id)
                logger.debug(f"[SSE] 无订阅者，清理任务：task_id={task_id}")
    
    async def broadcast(self, task_id: str, event: ProgressEvent) -> None:
        """
        向某个任务的所有订阅者广播事件
        
        Args:
            task_id: 任务 ID
            event: 进度事件对象
        """
        if task_id not in self._queues:
            logger.debug(f"[SSE] 无订阅者，跳过广播：task_id={task_id}")
            return
        
        dead_queues = []
        event_json = event.model_dump_json()
        
        for queue in self._queues[task_id]:
            try:
                # 非阻塞放入，如果队列满了则跳过（避免慢消费者拖快生产者）
                queue.put_nowait(f"data: {event_json}\n\n")
            except asyncio.QueueFull:
                logger.warning(f"[SSE] 队列已满，跳过：task_id={task_id}")
            except Exception as e:
                logger.error(f"[SSE] 广播失败：task_id={task_id}, error={e}")
                dead_queues.append(queue)
        
        # 清理失败的队列
        for queue in dead_queues:
            self.unsubscribe(task_id, queue)
    
    async def send_shot_event(self, task_id: str, shot_data: dict) -> None:
        """快捷方法：发送分镜生成完成事件"""
        event = ProgressEvent(
            event_type="shot_done",
            task_id=task_id,
            timestamp=datetime.now(),
            stage=f"shot_{shot_data.get('shot_id', 0)}",
            message=f"分镜 {shot_data.get('shot_id', 0)} 生成完成",
            media_files=[{
                "type": "image",
                "url": shot_data["image_url"],
                "description": shot_data.get("shot_name", f"分镜 {shot_data.get('shot_id')}"),
                "thumbnail_url": shot_data.get("image_url")  # 可以用缩略图
            }]
        )
        await self.broadcast(task_id, event)
    
    async def send_video_event(self, task_id: str, video_url: str, description: str = "生成视频") -> None:
        """快捷方法：发送视频生成完成事件"""
        event = ProgressEvent(
            event_type="video_done",
            task_id=task_id,
            timestamp=datetime.now(),
            stage="video",
            message="视频生成完成",
            media_files=[{
                "type": "video",
                "url": video_url,
                "description": description
            }]
        )
        await self.broadcast(task_id, event)
    
    async def send_completion(self, task_id: str, final_payload: dict) -> None:
        """发送任务完成事件"""
        event = ProgressEvent(
            event_type="completed",
            task_id=task_id,
            timestamp=datetime.now(),
            stage="final",
            message="任务完成",
            progress=1.0,
            payload=final_payload
        )
        await self.broadcast(task_id, event)
    
    async def send_error(self, task_id: str, error_message: str) -> None:
        """发送任务失败事件"""
        event = ProgressEvent(
            event_type="failed",
            task_id=task_id,
            timestamp=datetime.now(),
            stage="error",
            message=f"生成失败：{error_message}"
        )
        await self.broadcast(task_id, event)
    
    def get_active_count(self, task_id: str) -> int:
        """获取某个任务的活跃订阅者数量"""
        return len(self._queues.get(task_id, set()))


# 全局单例
sse_manager = SSEEventManager()
