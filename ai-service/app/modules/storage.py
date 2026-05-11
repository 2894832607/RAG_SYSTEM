"""
文件存储服务 - 管理生成的图像和视频文件

功能：
1. 下载远程 URL 的文件到本地
2. 提供公开访问的 URL
3. 按任务 ID 组织文件目录
"""
import aiohttp
import asyncio
from pathlib import Path
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class FileStorageService:
    """文件存储服务"""
    
    def __init__(self, base_dir: Optional[Path] = None):
        """
        Args:
            base_dir: 基础存储目录，默认为 ai-service/statics/outputs
        """
        if base_dir is None:
            base_dir = Path(__file__).resolve().parents[1] / "statics" / "outputs"
        
        self.base_dir = base_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)
        
        # 公开访问的基础 URL（根据实际部署环境调整）
        # 开发环境：http://localhost:8001/statics/outputs
        # 生产环境：https://your-domain.com/statics/outputs
        self.public_base_url = "/statics/outputs"
    
    def get_task_dir(self, task_id: str) -> Path:
        """获取任务的专属目录"""
        task_dir = self.base_dir / task_id
        task_dir.mkdir(parents=True, exist_ok=True)
        return task_dir
    
    async def download_file(
        self, 
        url: str, 
        task_id: str, 
        filename: str,
        file_type: str = "image"
    ) -> str:
        """
        下载文件到本地
        
        Args:
            url: 远程文件 URL
            task_id: 任务 ID
            filename: 保存的文件名
            file_type: 文件类型 (image/video)
            
        Returns:
            str: 公开访问的 URL
        """
        task_dir = self.get_task_dir(task_id)
        filepath = task_dir / filename
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    response.raise_for_status()
                    
                    # 写入文件
                    with open(filepath, 'wb') as f:
                        f.write(await response.read())
            
            logger.info(f"[Storage] 文件已保存：{filepath}")
            
            # 返回公开访问 URL
            public_url = f"{self.public_base_url}/{task_id}/{filename}"
            return public_url
            
        except Exception as e:
            logger.error(f"[Storage] 下载失败：url={url}, error={e}")
            # 如果下载失败，返回原始 URL（兜底策略）
            return url
    
    async def download_multiple(
        self,
        files: list[dict],
        task_id: str
    ) -> list[dict]:
        """
        批量下载多个文件
        
        Args:
            files: 文件列表 [{"type": "image", "url": "...", "description": "..."}]
            task_id: 任务 ID
            
        Returns:
            list[dict]: 本地化的文件信息
        """
        tasks = []
        
        for idx, file_info in enumerate(files):
            file_type = file_info.get("type", "image")
            url = file_info["url"]
            
            # 生成文件名
            ext = self._extract_extension(url)
            filename = f"{file_type}_{idx + 1}.{ext}"
            
            task = self.download_file(url, task_id, filename, file_type)
            tasks.append(task)
        
        # 并发下载
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 构建返回结果
        localized_files = []
        for idx, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"[Storage] 文件 {idx + 1} 下载失败：{result}")
                # 保留原 URL
                localized_files.append(files[idx])
            else:
                localized_files.append({
                    "type": files[idx]["type"],
                    "url": result,
                    "description": files[idx].get("description")
                })
        
        return localized_files
    
    def _extract_extension(self, url: str) -> str:
        """从 URL 提取文件扩展名"""
        from urllib.parse import urlparse
        
        parsed = urlparse(url)
        path = parsed.path.lower()
        
        if path.endswith('.png'):
            return 'png'
        elif path.endswith('.jpg') or path.endswith('.jpeg'):
            return 'jpg'
        elif path.endswith('.gif'):
            return 'gif'
        elif path.endswith('.webp'):
            return 'webp'
        elif path.endswith('.mp4'):
            return 'mp4'
        elif path.endswith('.mov'):
            return 'mov'
        elif path.endswith('.avi'):
            return 'avi'
        else:
            # 默认扩展名
            return 'png' if 'image' in url else 'mp4'


# 全局单例
storage_service = FileStorageService()
