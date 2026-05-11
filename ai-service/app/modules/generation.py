"""
图像生成客户端

支持多种图像生成提供商，通过 IMAGE_PROVIDER 环境变量配置：
  - cogview (默认): 调用 CogView-4-250304（/images/generations）
  - seedream: 调用豆包 Seedream 5.0
  - zhipu: 调用智谱 CogView（使用 zai-sdk）
  - disabled: 禁用图像生成，返回占位图 URL（适合本地开发）

Spec: specs/001-model-api-config/spec.md §3.4
"""
import asyncio
import os
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Optional

import aiohttp
import httpx

from app.config.model_config import get_image_config
from app.modules.cache import get_cache
from app.modules.cache_strategies import CacheStrategy
from app.modules.zhipu_client import ZhipuImageClient
from app.modules.cache_strategies import make_cache_key


# 本地静态输出目录（ai-service/statics/outputs/）
_OUTPUT_DIR = Path(__file__).resolve().parents[2] / "statics" / "outputs"
_PLACEHOLDER_URL = "/statics/outputs/placeholder.svg"


class CogViewClient:
    """图像生成客户端（OpenAI Images API 兼容）。

    配置通过 model_config.get_image_config() 读取：
      IMAGE_PROVIDER  — cogview（默认）/ seedream / disabled
      IMAGE_API_KEY   — 图像 API 密钥（缺省继承 LLM_API_KEY）
      IMAGE_BASE_URL  — 图像 API 端点（缺省继承 LLM_BASE_URL）
      IMAGE_MODEL     — 图像模型名称，默认 cogview-4-250304
      COGVIEW_SIZE    — 图像尺寸，默认 1024x1024
      COGVIEW_TIMEOUT — 超时秒数，默认 120
    
    Spec: specs/001-model-api-config/spec.md §3.4
    """

    def __init__(self) -> None:
        cfg = get_image_config()
        self.provider  = cfg.provider
        self.api_key   = cfg.api_key
        self.base_url  = cfg.base_url
        self.model     = cfg.model
        self.size      = cfg.size
        self.timeout   = cfg.timeout
        self._disabled = cfg.provider == "disabled"

    def is_enabled(self) -> bool:
        return bool(self.api_key) and not self._disabled

    # ------------------------------------------------------------------
    # 公共接口
    # ------------------------------------------------------------------

    def generate(self, prompt: str, negative_prompt: str = "", prev_frame_url: Optional[str] = None) -> str:
        """生成图像，返回可访问的 URL（优先本地路径）。

        IMAGE_PROVIDER=disabled 时直接返回占位图 URL，不调用远端 API。
        相同 prompt 前 64 字符命中缓存时直接返回上次生成的 URL。

        Args:
            prompt: 正向提示词
            negative_prompt: 负向提示词
            prev_frame_url: 上一帧图像 URL（Seedream 帧参考，录像Tier-2连贯性）

        步骤：
        1. 检查 Redis 缓存
        2. 调用图像 API，拿到 CDN URL
        3. 下载图片到 statics/outputs/{uuid}.png
        4. 将本地路径写入缓存后返回
        """
        if self._disabled:
            return _PLACEHOLDER_URL

        if self.provider == "local_sdxl":
            return self._call_local_sdxl(prompt, negative_prompt)

        if not self.api_key:
            raise RuntimeError("图像 API Key 未配置，请设置 IMAGE_API_KEY 或 LLM_API_KEY 环境变量")

        # ── 缓存读取 ──────────────────────────────────────────────
        cache = get_cache()
        cache_key = make_cache_key("image", prompt[:64], negative_prompt[:32], self.model)
        try:
            cached_url = cache.get(cache_key)
            if cached_url is not None:
                return cached_url
        except Exception as e:
            logger.warning(f"Cache get failed: {e}")

        # ── 实际生成 ──────────────────────────────────────────────
        cdn_url = self._call_api(prompt, negative_prompt, prev_frame_url=prev_frame_url)
        try:
            local_url = self._download(cdn_url)
        except Exception:
            # 下载失败时直接返回 CDN URL，前端仍可展示
            local_url = cdn_url

        # ── 写入缓存 ──────────────────────────────────────────────
        try:
            cache.set(cache_key, local_url, CacheStrategy.IMAGE_GENERATION_TTL)
        except Exception as e:
            logger.warning(f"Cache set failed: {e}")
            
        return local_url
    
    def _call_seedream(self, prompt: str, negative_prompt: str = "", prev_frame_url: Optional[str] = None) -> str:
        """调用豆包 Seedream 5.0 API 生成图像。
        
        Spec: test_doubao_image_rest.py (验证通过的调用方式)
        Endpoint: https://ark.cn-beijing.volces.com/api/v3/images/generations
        Model: doubao-seedream-5-0-260128 或 doubao-seedream-5-0-lite-260128
        Size: 必须 >= 3686400 像素 (如 1920x1920)
        
        Args:
            prompt: 正向提示词
            negative_prompt: 负向提示词（豆包暂不支持）
            prev_frame_url: 上一帧图像 URL（用于连贯性生成）
        
        Returns:
            CDN URL 字符串
        """
        import httpx
        import time
        import random
        
        url = "https://ark.cn-beijing.volces.com/api/v3/images/generations"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        
        # 构建请求体
        payload = {
            "model": self.model or "doubao-seedream-5-0-lite-260128",
            "prompt": prompt,
            "sequential_image_generation": "disabled",
            "response_format": "url",
            "size": "2K",  # 豆包推荐尺寸
            "stream": False,
            "watermark": True
        }
        
        # 如果有 prev_frame_url，添加帧参考（录像 Tier-2 连贯性）
        if prev_frame_url:
            payload["reference_image"] = {"url": prev_frame_url}
        
        # 指数退避重试逻辑（处理 429 Rate Limit）
        max_retries = 5
        base_delay = 5.0  # 初始等待 5 秒
        max_delay = 120.0  # 最多等待 120 秒
        
        for attempt in range(max_retries + 1):
            try:
                logger.info("[Seedream] 调用 API (尝试 %d/%d): %s", attempt + 1, max_retries + 1, prompt[:50])
                
                with httpx.Client(timeout=None) as client:
                    response = client.post(url, json=payload, headers=headers)
                    
                    # 检查是否为 429 错误
                    if response.status_code == 429:
                        retry_after = response.headers.get("Retry-After")
                        if retry_after:
                            wait_time = float(retry_after)
                        else:
                            # 指数退避计算：delay = base_delay * (2 ^ attempt) + jitter
                            exponential_delay = base_delay * (2 ** attempt)
                            jitter = random.uniform(0, 2)  # 添加 0-2 秒随机抖动
                            wait_time = min(exponential_delay + jitter, max_delay)
                        
                        logger.warning("[Seedream] 触发频率限制 (429)，等待 %.1f 秒后重试...", wait_time)
                        time.sleep(wait_time)
                        continue
                    
                    response.raise_for_status()
                    result = response.json()
                
                # 解析响应
                if 'data' in result and len(result['data']) > 0:
                    img_data = result['data'][0]
                    cdn_url = img_data.get('url', '')
                    if not cdn_url and 'image_url' in img_data:
                        cdn_url = img_data['image_url'].get('url', '')
                    
                    if cdn_url:
                        logger.info("[Seedream] 生成成功：%s", cdn_url[:80])
                        return cdn_url
                
                raise RuntimeError(f"豆包图像生成返回数据格式异常：{result}")
                
            except httpx.HTTPStatusError as e:
                # 非 429 错误直接抛出
                logger.error("[Seedream] HTTP 错误：%d - %s", e.response.status_code, e.response.text)
                raise RuntimeError(f"豆包图像生成 HTTP 错误：{e.response.status_code}")
            except Exception as e:
                logger.error("[Seedream] 生成失败：%s", str(e))
                raise RuntimeError(f"豆包图像生成失败：{str(e)}")
        
        # 所有重试都失败
        raise RuntimeError(f"豆包图像生成：达到最大重试次数 ({max_retries})，可能触达 API 配额限制")

    async def generate_scene_async(self, scene) -> dict:
        """
        异步生成单个场景图像
        
        Args:
            scene: ScenePrompt 对象
            
        Returns:
            dict: {"scene": int, "desc": str, "image_url": str, "positive": str, "negative": str}
        """
        try:
            url = await self.generate_async(scene.positive, negative_prompt=scene.negative)
            return {
                "scene": scene.scene,
                "desc": scene.desc,
                "image_url": url,
                "positive": scene.positive,
                "negative": scene.negative,
            }
        except Exception as exc:
            return {
                "scene": scene.scene,
                "desc": scene.desc,
                "image_url": "",
                "positive": scene.positive,
                "negative": scene.negative,
                "error": str(exc)
            }
    
    async def generate_async(self, prompt: str, negative_prompt: str = "", prev_frame_url: Optional[str] = None) -> str:
        """异步版本：生成图像，返回可访问的 URL。
        
        使用 aiohttp 进行异步 HTTP 请求，适合高并发场景。
        """
        if self._disabled:
            return _PLACEHOLDER_URL

        if self.provider == "local_sdxl":
            # 本地 SDXL 暂不支持异步
            return self._call_local_sdxl(prompt, negative_prompt)

        if not self.api_key:
            raise RuntimeError("图像 API Key 未配置，请设置 IMAGE_API_KEY 或 LLM_API_KEY 环境变量")

        # 缓存读取（同步，但很快）
        cache = get_cache()
        cache_key = make_cache_key("image", prompt[:64], negative_prompt[:32], self.model)
        try:
            cached_url = cache.get(cache_key)
            if cached_url is not None:
                return cached_url
        except Exception as e:
            pass

        # 异步调用 API
        cdn_url = await self._call_api_async(prompt, negative_prompt, prev_frame_url)
        
        try:
            local_url = await self._download_async(cdn_url)
        except Exception:
            local_url = cdn_url

        # 写入缓存
        try:
            cache.set(cache_key, local_url, CacheStrategy.IMAGE_GENERATION_TTL)
        except Exception as e:
            pass
            
        return local_url
    
    async def _call_api_async(self, prompt: str, negative_prompt: str = "", prev_frame_url: Optional[str] = None) -> str:
        """异步调用图像生成 API"""
        # 智谱 SDK 调用（同步阻塞，放线程池）
        if self.provider == "zhipu":
            zhipu_client = ZhipuImageClient()
            if zhipu_client.is_enabled():
                loop = asyncio.get_event_loop()
                return await loop.run_in_executor(
                    None, 
                    lambda: zhipu_client.generate(prompt, negative_prompt)
                )
            else:
                raise RuntimeError("智谱 SDK 未启用，请安装 zai-sdk 并配置 API Key")
        
        # 豆包/智谱 HTTP API 异步调用
        url = f"{self.base_url}/images/generations"
        payload: dict = {
            "model": self.model,
            "prompt": prompt,
            "size": self.size,
        }
        if negative_prompt.strip():
            payload["negative_prompt"] = negative_prompt
        if self.provider == "seedream":
            payload["response_format"] = "url"
            payload["watermark"] = True
            payload["sequential_image_generation"] = "disabled"
            payload["stream"] = False
            if prev_frame_url:
                payload["image_url"] = prev_frame_url
                payload["strength"] = float(os.getenv("VIDEO_IMAGE_STRENGTH", "0.65"))
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        
        # 异步重试逻辑
        last_exc: Exception | None = None
        for attempt in range(3):
            try:
                async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout)) as session:
                    async with session.post(url, json=payload, headers=headers) as resp:
                        if resp.status != 200:
                            resp.raise_for_status()
                        data = await resp.json()
                        break
            except aiohttp.ClientResponseError as exc:
                last_exc = exc
                code = exc.status if exc.status else 0
                if code in (429, 500, 502, 503, 504) and attempt < 2:
                    await asyncio.sleep(1.2 * (attempt + 1))
                    continue
                if code == 429 and self.provider == "cogview":
                    # 异步回退
                    fallback_url = await self._fallback_seedream_async(prompt, negative_prompt, prev_frame_url)
                    if fallback_url:
                        return fallback_url
                raise
            except Exception as exc:
                last_exc = exc
                if attempt < 2:
                    await asyncio.sleep(1.0 * (attempt + 1))
                    continue
                raise

        if data is None:
            if last_exc is not None:
                raise last_exc
            raise RuntimeError("图像生成失败：未获取到有效响应")

        images = data.get("data") or []
        if not images or not images[0].get("url"):
            raise RuntimeError(f"图像生成 API 返回结构异常（{self.provider}）：{data}")
        return images[0]["url"]
    
    async def _download_async(self, cdn_url: str) -> str:
        """异步下载图像到本地"""
        output_path = _OUTPUT_DIR / f"{uuid.uuid4().hex}.png"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(cdn_url) as resp:
                    resp.raise_for_status()
                    with open(output_path, 'wb') as f:
                        f.write(await resp.read())
            
            # 返回相对路径 URL
            return f"/statics/outputs/{output_path.name}"
        except Exception:
            # 下载失败返回原 URL
            return cdn_url
    
    async def _fallback_seedream_async(self, prompt: str, negative_prompt: str, prev_frame_url: Optional[str]) -> Optional[str]:
        """异步回退到豆包 API"""
        try:
            # 临时切换到豆包配置
            original_provider = self.provider
            self.provider = "seedream"
            url = await self._call_api_async(prompt, negative_prompt, prev_frame_url)
            self.provider = original_provider
            return url
        except Exception:
            self.provider = original_provider
            return None

    def generate_scenes(self, scenes: list) -> list[dict]:
        """并行生成多场景图片，返回结果列表，顺序与 scenes 一致。

        Args:
            scenes: list[ScenePrompt] — 由 PromptEnhancer.split_scenes() 返回

        Returns:
            list of {"scene": int, "desc": str, "image_url": str, "positive": str, "negative": str}
            生成失败的场景 image_url 为空字符串，不影响其他场景。
        """
        results: list[dict] = [None] * len(scenes)  # type: ignore[list-item]

        def _generate_one(idx: int, scene) -> tuple[int, dict]:
            try:
                url = self.generate(scene.positive, negative_prompt=scene.negative)
            except Exception as exc:
                url = ""
            return idx, {
                "scene": scene.scene,
                "desc": scene.desc,
                "image_url": url,
                "positive": scene.positive,
                "negative": scene.negative,
            }

        # 本地 SDXL 全内存运行，不支持并发推理，串行执行防止 GPU 竞争
        # 云端 API 支持并发，最多 5 线程同时请求
        if self.provider == "local_sdxl":
            for i, s in enumerate(scenes):
                _, result = _generate_one(i, s)
                results[i] = result
        else:
            max_workers = min(len(scenes), 5)
            with ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="gen-scene") as pool:
                futures = {pool.submit(_generate_one, i, s): i for i, s in enumerate(scenes)}
                for future in as_completed(futures):
                    idx, result = future.result()
                    results[idx] = result

        return results

    # ------------------------------------------------------------------
    # 私有方法
    # ------------------------------------------------------------------

    def _call_api(self, prompt: str, negative_prompt: str = "", prev_frame_url: Optional[str] = None) -> str:
        """调用图像生成 API，支持限流重试与 provider 回退。"""
        # 智谱 SDK 调用
        if self.provider == "zhipu":
            zhipu_client = ZhipuImageClient()
            if zhipu_client.is_enabled():
                return zhipu_client.generate(prompt, negative_prompt)
            else:
                raise RuntimeError("智谱 SDK 未启用，请安装 zai-sdk 并配置 API Key")
        
        # 豆包/智谱 HTTP API 调用
        url = f"{self.base_url}/images/generations"
        payload: dict = {
            "model": self.model,
            "prompt": prompt,
            "size": self.size,
        }
        if negative_prompt.strip():
            payload["negative_prompt"] = negative_prompt
        # Doubao Seedream 额外参数
        if self.provider == "seedream":
            payload["response_format"] = "url"
            payload["watermark"] = True
            payload["sequential_image_generation"] = "disabled"
            payload["stream"] = False
            if prev_frame_url:                       # Tier-2 帧参考（默认启用）
                payload["image_url"] = prev_frame_url
                payload["strength"] = float(os.getenv("VIDEO_IMAGE_STRENGTH", "0.65"))
        # CogView HTTP API 参数
        elif self.provider == "cogview":
            pass  # 使用默认参数
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        data = None
        last_exc: Exception | None = None
        # 429/5xx 在高峰期较常见，做短退避重试。
        for attempt in range(3):
            try:
                with httpx.Client(timeout=None, trust_env=False) as client:
                    resp = client.post(url, json=payload, headers=headers)
                    resp.raise_for_status()
                    data = resp.json()
                    break
            except httpx.HTTPStatusError as exc:
                last_exc = exc
                code = exc.response.status_code if exc.response is not None else 0
                if code in (429, 500, 502, 503, 504) and attempt < 2:
                    time.sleep(1.2 * (attempt + 1))
                    continue
                # CogView 限流时自动回退到 Seedream（需要 ARK key）
                if code == 429 and self.provider == "cogview":
                    fallback_url = self._fallback_seedream(prompt, negative_prompt, prev_frame_url)
                    if fallback_url:
                        return fallback_url
                raise
            except Exception as exc:
                last_exc = exc
                if attempt < 2:
                    time.sleep(1.0 * (attempt + 1))
                    continue
                raise

        if data is None:
            if last_exc is not None:
                raise last_exc
            raise RuntimeError("图像生成失败：未获取到有效响应")

        images = data.get("data") or []
        if not images or not images[0].get("url"):
            raise RuntimeError(f"图像生成 API 返回结构异常（{self.provider}）：{data}")
        return images[0]["url"]

    def _call_local_sdxl(self, prompt: str, negative_prompt: str = "") -> str:
        """调用本地 SDXL-Turbo 服务（http://localhost:8090），返回本地图片路径。"""
        cache = get_cache()
        cache_key = make_cache_key("image", prompt[:64], negative_prompt[:32], "local_sdxl")
        cached_url = cache.get(cache_key)
        if cached_url is not None:
            return cached_url

        payload = {
            "prompt": prompt,
            "negative_prompt": negative_prompt,
            "size": self.size,
        }
        with httpx.Client(timeout=None, trust_env=False) as client:
            resp = client.post(self.base_url, json=payload)
            resp.raise_for_status()
            data = resp.json()

        # serve.py 返回 {"data": [{"b64_json": "..."}], "saved_path": "..."}
        saved_path: str = data.get("saved_path", "")
        if not saved_path:
            raise RuntimeError(f"local_sdxl 返回结构异常：{data}")

        # 转成前端可访问的 /statics/outputs/{filename}
        filename = Path(saved_path).name
        local_url = f"/statics/outputs/{filename}"

        try:
            cache.set(cache_key, local_url, CacheStrategy.IMAGE_GENERATION_TTL)
        except Exception as e:
            logger.warning(f"Cache set failed: {e}")
        return local_url

    def _fallback_seedream(self, prompt: str, negative_prompt: str = "", prev_frame_url: Optional[str] = None) -> Optional[str]:
        """CogView 限流时回退到 Seedream；失败时返回 None。"""
        ark_key = (os.getenv("ARK_API_KEY") or "").strip()
        if not ark_key:
            return None

        base = "https://ark.cn-beijing.volces.com/api/v3"
        model = "doubao-seedream-5-0-260128"
        payload: dict = {
            "model": model,
            "prompt": prompt,
            "size": "2K",
            "response_format": "url",
            "watermark": True,
        }
        if negative_prompt.strip():
            payload["negative_prompt"] = negative_prompt
        if prev_frame_url:
            payload["image_url"] = prev_frame_url
            payload["strength"] = float(os.getenv("VIDEO_IMAGE_STRENGTH", "0.65"))

        headers = {
            "Authorization": f"Bearer {ark_key}",
            "Content-Type": "application/json",
        }
        with httpx.Client(timeout=None, trust_env=False) as client:
            resp = client.post(f"{base}/images/generations", json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
        images = data.get("data") or []
        if not images or not images[0].get("url"):
            return None
        return images[0]["url"]

    def _download(self, cdn_url: str) -> str:
        """下载图片到本地，返回 /statics/outputs/{uuid}.png。"""
        _OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        image_name = f"{uuid.uuid4()}.png"
        dest = _OUTPUT_DIR / image_name

        with httpx.Client(timeout=None, trust_env=False) as client:
            resp = client.get(cdn_url)
            resp.raise_for_status()
            dest.write_bytes(resp.content)

        return f"/statics/outputs/{image_name}"


# 向后兼容旧名称（pipeline.py 仍使用 DiffusionClient）
DiffusionClient = CogViewClient
