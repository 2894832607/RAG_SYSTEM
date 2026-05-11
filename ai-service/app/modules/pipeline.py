import asyncio
import httpx
from datetime import datetime
from pathlib import Path

from app.modules.generation import CogViewClient
from app.modules.prompt import PromptEnhancer
from app.modules.retriever import Retriever
from app.modules.sse_manager import sse_manager
from app.modules.storage import storage_service
from app.schemas.requests import (
    CallbackBody, 
    CallbackPayload, 
    GenerationRequest, 
    SimpleGenerationResponse,
    MediaFile,
    ProgressEvent
)


def generate_once(source_text: str) -> SimpleGenerationResponse:
    """同步版本 - 用于简单测试"""
    retriever = Retriever()

    # 混合检索：自动判断精准/模糊模式
    result = retriever.smart_retrieve(source_text)
    poems = result.poems

    # 将召回诗词格式化为知识块列表
    knowledge_blocks = [p.to_knowledge_block() for p in poems]

    # 取相似度最高的一首作为展示用 retrievedText
    best = poems[0] if poems else None
    retrieved_display = (
        f"【{best.dynasty}·{best.author}·《{best.title}》】\n{best.original_poem}"
        if best else source_text
    )

    # 多场景拆分 + 提示词增强（与主聊天路径对齐）
    scenes = PromptEnhancer().split_scenes(source_text, knowledge_blocks)
    scene_results = CogViewClient().generate_scenes(scenes)

    # 取第一张有效图片作为主图（兼容 SimpleGenerationResponse schema）
    first = next((r for r in scene_results if r.get("image_url")), None)
    image_url = first["image_url"] if first else ""
    positive_prompt = first["positive"] if first else ""
    negative_prompt = first["negative"] if first else ""

    return SimpleGenerationResponse(
        retrievedText=retrieved_display,
        enhancedPrompt=positive_prompt,
        negativePrompt=negative_prompt,
        imageUrl=image_url,
    )


async def run_generation_async(request: GenerationRequest) -> None:
    """
    异步版本 - 支持 SSE 实时推送
    
    流程：
    1. 发送 started 事件
    2. RAG 检索完成 → 发送 retrieval_done 事件
    3. 每张图生成完成 → 发送 shot_done 事件（含 image_url）
    4. 视频生成完成 → 发送 video_done 事件
    5. 全部完成 → 发送 completed 事件
    """
    task_id = request.taskId
    
    try:
        # Step 1: 发送开始事件
        await sse_manager.broadcast(task_id, ProgressEvent(
            event_type="started",
            task_id=task_id,
            timestamp=datetime.now(),
            stage="init",
            message="任务已开始，正在检索诗词库...",
            progress=0.0
        ))
        
        # Step 2: RAG 检索
        retriever = Retriever()
        result = retriever.smart_retrieve(request.poemText)
        poems = result.poems
        
        knowledge_blocks = [p.to_knowledge_block() for p in poems]
        
        best = poems[0] if poems else None
        retrieved_display = (
            f"【{best.dynasty}·{best.author}·《{best.title}》】\n{best.original_poem}"
            if best else request.poemText
        )
        
        # 发送检索完成事件
        await sse_manager.broadcast(task_id, ProgressEvent(
            event_type="retrieval_done",
            task_id=task_id,
            timestamp=datetime.now(),
            stage="retrieval",
            message=f"已找到 {len(poems)} 首相关诗词",
            progress=0.2,
            payload={"retrievedText": retrieved_display}
        ))
        
        # Step 3: 分镜生成
        scenes = PromptEnhancer().split_scenes(request.poemText, knowledge_blocks)
        cogview = CogViewClient()
        
        media_files = []
        total_scenes = len(scenes)
        
        for idx, scene in enumerate(scenes):
            try:
                # 生成单张分镜
                shot_result = await cogview.generate_scene_async(scene)
                
                if shot_result.get("image_url"):
                    # 下载并保存文件到本地
                    local_url = await storage_service.download_file(
                        shot_result["image_url"],
                        task_id,
                        f"shot_{idx + 1}.png",
                        "image"
                    )
                    
                    # 构建媒体文件信息
                    media_file = MediaFile(
                        type="image",
                        url=local_url,
                        description=f"分镜 {idx + 1}: {scene.get('scene_description', '')[:50]}...",
                        thumbnail_url=local_url
                    )
                    media_files.append(media_file)
                    
                    # 发送 shot_done 事件（实时推送！包含提示词）
                    await sse_manager.send_shot_event(task_id, {
                        "shot_id": idx + 1,
                        "shot_name": f"分镜 {idx + 1}",
                        "image_url": local_url,
                        "positive": shot_result.get("positive", ""),
                        "negative": shot_result.get("negative", ""),
                        "scene_description": scene.get("scene_description", "")
                    })
                
                # 更新进度
                progress = 0.2 + (0.6 * (idx + 1) / total_scenes)
                await sse_manager.broadcast(task_id, ProgressEvent(
                    event_type="shot_done",
                    task_id=task_id,
                    timestamp=datetime.now(),
                    stage=f"shot_{idx + 1}",
                    message=f"分镜 {idx + 1} 生成完成",
                    progress=progress,
                    media_files=[media_file] if media_file else None
                ))
                
            except Exception as e:
                # 单张分镜失败不影响其他分镜
                await sse_manager.broadcast(task_id, ProgressEvent(
                    event_type="shot_done",
                    task_id=task_id,
                    timestamp=datetime.now(),
                    stage=f"shot_{idx + 1}_error",
                    message=f"分镜 {idx + 1} 生成失败：{str(e)}",
                    progress=0.2 + (0.6 * (idx + 1) / total_scenes)
                ))
        
        # Step 4: 如果有视频生成需求（预留）
        # TODO: 集成豆包/智谱视频生成
        # if need_video:
        #     video_url = await generate_video(...)
        #     local_video_url = await storage_service.download_file(...)
        #     await sse_manager.send_video_event(task_id, local_video_url, "生成视频")
        
        # Step 5: 发送完成事件（包含完整的 enhancedPrompt）
        final_payload = {
            "retrievedText": retrieved_display,
            "enhancedPrompt": media_files[0].description if media_files else "",
            "imageUrl": media_files[0].url if media_files else "",
            "mediaFiles": [mf.model_dump() for mf in media_files]
        }
        
        # 额外广播一条包含所有分镜提示词的 completion 事件
        all_prompts = []
        for i, mf in enumerate(media_files):
            all_prompts.append({
                "shot_id": i + 1,
                "positive": mf.description,
                "negative": getattr(mf, 'negative_prompt', '') if hasattr(mf, 'negative_prompt') else ''
            })
        final_payload["allPrompts"] = all_prompts
        
        await sse_manager.send_completion(task_id, final_payload)
        
        # Step 6: 传统回调（兼容性保留）
        if media_files:
            # 收集所有图片 URLs
            all_image_urls = [mf.url for mf in media_files if mf.type == "image"]
            
            asyncio.create_task(send_callback_async(
                callback_url=str(request.callbackUrl),
                callback_token=request.callbackToken,
                body=CallbackBody(
                    taskId=task_id,
                    status=1,
                    payload=CallbackPayload(
                        retrievedText=retrieved_display,
                        enhancedPrompt=media_files[0].description if media_files else "",
                        imageUrl=all_image_urls[0] if all_image_urls else "",  # 主图（第一张，向后兼容）
                        imageUrls=all_image_urls if all_image_urls else None,  # 所有图片（新字段）
                        negativePrompt=getattr(media_files[0], 'negative_prompt', '') if media_files else None,
                    )
                )
            ))
        
    except Exception as exc:
        # 发送失败事件
        await sse_manager.send_error(task_id, str(exc))
        
        # 传统回调（失败）
        asyncio.create_task(send_callback_async(
            callback_url=str(request.callbackUrl),
            callback_token=request.callbackToken,
            body=CallbackBody(
                taskId=task_id,
                status=2,
                errorMessage=str(exc)
            )
        ))


def run_generation(request: GenerationRequest) -> None:
    """同步包装器 - 向后兼容"""
    try:
        # 在新的事件循环中运行异步版本
        asyncio.run(run_generation_async(request))
    except RuntimeError:
        # 如果已经在事件循环中（不会发生，因为这是背景线程）
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(run_generation_async(request))
        loop.close()


async def send_callback_async(callback_url: str, callback_token: str, body: CallbackBody) -> None:
    """异步发送回调"""
    try:
        async with httpx.AsyncClient(timeout=60.0, trust_env=False) as client:
            response = await client.post(
                callback_url,
                json=body.model_dump(exclude_none=True),
                headers={"X-Callback-Token": callback_token}
            )
            response.raise_for_status()
    except Exception as e:
        # 回调失败不影响 SSE 推送
        pass


def send_callback(callback_url: str, callback_token: str, body: CallbackBody) -> None:
    """同步版本 - 保留向后兼容"""
    with httpx.Client(timeout=60.0, trust_env=False) as client:
        response = client.post(
            callback_url,
            json=body.model_dump(exclude_none=True),
            headers={"X-Callback-Token": callback_token}
        )
        response.raise_for_status()
