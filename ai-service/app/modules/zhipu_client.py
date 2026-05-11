"""
智谱 AI 客户端（使用 zai-sdk）

支持：
  - 图像生成：cogview-4-250304, glm-image
  - 视频生成：cogvideox-3

Spec: .specify/memory/constitution.md §3.9 智谱 SDK 接口规范
"""
import logging
import time
from pathlib import Path
from typing import Optional

from app.config.model_config import get_image_config, get_video_config

logger = logging.getLogger(__name__)

# 本地静态输出目录
_OUTPUT_DIR = Path(__file__).resolve().parents[2] / "statics" / "outputs"


class ZhipuImageClient:
    """
    智谱图像生成客户端（zai-sdk）。
    
    调用示例：
        client = ZhipuImageClient()
        url = client.generate("一只可爱的小猫咪")
    """
    
    def __init__(self) -> None:
        cfg = get_image_config()
        self.api_key = cfg.api_key
        self.model = cfg.model
        self.size = cfg.size
        self.timeout = cfg.timeout
        
        # 延迟导入 zai-sdk，避免未安装时报错
        try:
            from zai import ZhipuAiClient
            self.client = ZhipuAiClient(api_key=self.api_key)
            self._enabled = True
        except ImportError:
            logger.warning("zai-sdk 未安装，运行 pip install zai-sdk 后启用智谱图像生成")
            self.client = None
            self._enabled = False
    
    def is_enabled(self) -> bool:
        return self._enabled and bool(self.api_key)
    
    def generate(self, prompt: str, negative_prompt: str = "") -> str:
        """
        生成图像，返回本地文件路径。
        
        Args:
            prompt: 正向提示词
            negative_prompt: 负向提示词（智谱暂不支持）
        
        Returns:
            本地图片路径字符串
        
        Raises:
            RuntimeError: SDK 未安装或 API 调用失败
        """
        if not self.is_enabled():
            raise RuntimeError("智谱图像生成未启用，请安装 zai-sdk 并配置 API Key")
        
        logger.info("[ZhipuImage] 开始生成 image: model=%s, size=%s", self.model, self.size)
        
        try:
            # 调用智谱图像生成 API
            response = self.client.images.generations(
                model=self.model,
                prompt=prompt,
            )
            
            # 获取 CDN URL
            cdn_url = response.data[0].url
            logger.info("[ZhipuImage] CDN URL: %s", cdn_url)
            
            # 下载到本地
            local_url = self._download(cdn_url)
            logger.info("[ZhipuImage] 已保存到本地：%s", local_url)
            
            return local_url
            
        except Exception as e:
            logger.error("[ZhipuImage] 生成失败：%s", str(e))
            raise RuntimeError(f"智谱图像生成失败：{str(e)}")
    
    def _download(self, cdn_url: str) -> str:
        """下载 CDN 图片到本地，返回本地路径。"""
        import httpx
        
        _OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        filename = f"zhipu_img_{int(time.time())}.png"
        local_path = _OUTPUT_DIR / filename
        
        with httpx.Client(timeout=None) as client:
            resp = client.get(cdn_url)
            resp.raise_for_status()
            local_path.write_bytes(resp.content)
        
        # 返回相对路径 URL
        return f"/statics/outputs/{filename}"


class ZhipuVideoClient:
    """
    智谱视频生成客户端（zai-sdk）。
    
    异步轮询机制：
        1. 创建任务 → 获取 task_id
        2. 轮询状态 → 等待 SUCCESS
        3. 下载视频 → 返回本地路径
    
    调用示例：
        client = ZhipuVideoClient()
        url = client.generate("一只猫在玩耍", with_audio=True)
    """
    
    def __init__(
        self,
        timeout: int = 300,
        poll_interval: int = 5,
    ) -> None:
        cfg = get_video_config()
        self.api_key = cfg.api_key
        self.model = cfg.model
        self.timeout = timeout
        self.poll_interval = poll_interval
        
        # 延迟导入 zai-sdk
        try:
            from zai import ZhipuAiClient
            self.client = ZhipuAiClient(api_key=self.api_key)
            self._enabled = True
        except ImportError:
            logger.warning("zai-sdk 未安装，运行 pip install zai-sdk 后启用智谱视频生成")
            self.client = None
            self._enabled = False
    
    def is_enabled(self) -> bool:
        return self._enabled and bool(self.api_key)
    
    def generate(
        self,
        prompt: str,
        quality: str = "quality",
        with_audio: bool = True,
        size: str = "1920x1080",
        fps: int = 30,
    ) -> str:
        """
        生成视频，返回本地文件路径。
        
        Args:
            prompt: 视频内容描述
            quality: 输出模式 "quality" 或 "speed"
            with_audio: 是否包含音频
            size: 视频分辨率，如 "1920x1080" 或 "3840x2160"
            fps: 帧率 30 或 60
        
        Returns:
            本地视频路径字符串
        
        Raises:
            RuntimeError: SDK 未安装或 API 调用失败
        """
        if not self.is_enabled():
            raise RuntimeError("智谱视频生成未启用，请安装 zai-sdk 并配置 API Key")
        
        logger.info(
            "[ZhipuVideo] 开始生成 video: model=%s, size=%s, fps=%s",
            self.model, size, fps
        )
        
        try:
            # 1. 创建视频生成任务
            response = self.client.videos.generations(
                model=self.model,
                prompt=prompt,
                quality=quality,
                with_audio=with_audio,
                size=size,
                fps=fps,
            )
            
            task_id = response.id
            logger.info("[ZhipuVideo] 任务已创建 task_id=%s", task_id)
            
            # 2. 轮询结果
            video_url = self._poll_task(task_id)
            logger.info("[ZhipuVideo] 视频生成成功：%s", video_url)
            
            # 3. 下载到本地
            local_url = self._download(video_url)
            logger.info("[ZhipuVideo] 已保存到本地：%s", local_url)
            
            return local_url
            
        except Exception as e:
            logger.error("[ZhipuVideo] 生成失败：%s", str(e))
            raise RuntimeError(f"智谱视频生成失败：{str(e)}")
    
    def _poll_task(self, task_id: str) -> str:
        """轮询视频生成任务直到完成。"""
        start_time = time.time()
        
        while True:
            elapsed = time.time() - start_time
            if elapsed > self.timeout:
                raise RuntimeError(f"视频生成超时（{self.timeout}秒）")
            
            try:
                result = self.client.videos.retrieve_videos_result(id=task_id)
                status = result.status
                
                if status == "SUCCESS":
                    return result.video_url
                elif status == "FAILED":
                    raise RuntimeError(f"视频生成失败：{getattr(result, 'error', 'Unknown error')}")
                else:
                    logger.info("[ZhipuVideo] 任务进行中 status=%s, 等待 %s 秒...", status, self.poll_interval)
                    time.sleep(self.poll_interval)
                    
            except Exception as e:
                logger.warning("[ZhipuVideo] 轮询失败：%s，重试...", str(e))
                time.sleep(self.poll_interval)
    
    def _download(self, video_url: str) -> str:
        """下载 CDN 视频到本地，返回本地路径。"""
        import httpx
        
        _OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        filename = f"zhipu_vid_{int(time.time())}.mp4"
        local_path = _OUTPUT_DIR / filename
        
        with httpx.Client(timeout=None) as client:
            resp = client.get(video_url)
            resp.raise_for_status()
            local_path.write_bytes(resp.content)
        
        # 返回相对路径 URL
        return f"/statics/outputs/{filename}"
