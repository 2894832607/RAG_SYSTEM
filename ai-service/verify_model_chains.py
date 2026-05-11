#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
验证前端模型切换时，LLM/Image/Video 三个链路是否使用正确的 API Key

预期行为：
- 选择 GLM 时：三个链路都应该使用 GLM_API_KEY (a76aae89...)
- 选择豆包时：三个链路都应该使用 ARK_API_KEY (a9610f41...)
"""

import os
import sys
from pathlib import Path

# 添加 ai-service 到路径
sys.path.insert(0, str(Path(__file__).parent / "ai-service"))

from dotenv import load_dotenv
from app.config.model_config import get_llm_config, get_image_config, get_video_config

# 加载 .env.local
env_file = Path(__file__).parent / "ai-service" / ".env.local"
if env_file.exists():
    load_dotenv(env_file)
    print(f"✅ 已加载环境配置：{env_file}\n")
else:
    print(f"⚠️  未找到 .env.local 文件\n")

print("=" * 80)
print("📊 当前配置验证")
print("=" * 80)

# 1. LLM 配置
llm_cfg = get_llm_config()
print(f"\n【LLM 链路】")
print(f"  Provider:    {llm_cfg.provider}")
print(f"  Model:       {llm_cfg.model}")
print(f"  Base URL:    {llm_cfg.base_url}")
print(f"  API Key:     {llm_cfg.api_key[:8]}...{llm_cfg.api_key[-4:] if llm_cfg.api_key else ''}")
print(f"  预期 Key:    a76aae89... (GLM)")
print(f"  匹配度:      {'✅ 正确' if llm_cfg.api_key.startswith('a76aae89') else '❌ 错误'}")

# 2. Image 配置
img_cfg = get_image_config()
print(f"\n【Image 链路】")
print(f"  Provider:    {img_cfg.provider}")
print(f"  Model:       {img_cfg.model}")
print(f"  Base URL:    {img_cfg.base_url}")
print(f"  API Key:     {img_cfg.api_key[:8]}...{img_cfg.api_key[-4:] if img_cfg.api_key else ''}")
print(f"  预期 Key:    a76aae89... (GLM) 或 a9610f41... (豆包)")
print(f"  来源：       {'IMAGE_API_KEY' if os.getenv('IMAGE_API_KEY') else '继承 LLM_API_KEY'}")

# 3. Video 配置
video_cfg = get_video_config()
print(f"\n【Video 链路】")
print(f"  Provider:    {video_cfg.provider}")
print(f"  Model:       {video_cfg.model}")
print(f"  Base URL:    {video_cfg.base_url}")
print(f"  API Key:     {video_cfg.api_key[:8]}...{video_cfg.api_key[-4:] if video_cfg.api_key else ''}")
print(f"  预期 Key:    a76aae89... (GLM) 或 a9610f41... (豆包)")
print(f"  来源：       {'VIDEO_API_KEY' if os.getenv('VIDEO_API_KEY') else '继承 IMAGE_API_KEY' if os.getenv('IMAGE_API_KEY') else '继承 LLM_API_KEY'}")

# 4. 一致性检查
print(f"\n{'=' * 80}")
print("🔗 链路一致性检查")
print("=" * 80)

llm_key_prefix = llm_cfg.api_key[:8] if llm_cfg.api_key else ""
img_key_prefix = img_cfg.api_key[:8] if img_cfg.api_key else ""
video_key_prefix = video_cfg.api_key[:8] if video_cfg.api_key else ""

print(f"\nLLM Key 前缀:   {llm_key_prefix or '(空)'}")
print(f"Image Key 前缀：{img_key_prefix or '(空)'}")
print(f"Video Key 前缀：{video_key_prefix or '(空)'}")

if llm_key_prefix == img_key_prefix == video_key_prefix:
    print(f"\n✅ 三个链路使用相同的 API Key！")
else:
    print(f"\n⚠️  三个链路的 API Key 不一致！")
    if llm_key_prefix != img_key_prefix:
        print(f"   - LLM 和 Image 的 Key 不同")
    if img_key_prefix != video_key_prefix:
        print(f"   - Image 和 Video 的 Key 不同")

# 5. 环境变量详细检查
print(f"\n{'=' * 80}")
print("📋 环境变量详情")
print("=" * 80)

env_vars = [
    "LLM_API_KEY",
    "LLM_PROVIDER",
    "LLM_MODEL",
    "IMAGE_API_KEY",
    "IMAGE_PROVIDER",
    "IMAGE_MODEL",
    "VIDEO_API_KEY",
    "VIDEO_PROVIDER",
    "VIDEO_MODEL",
    "ARK_API_KEY",
    "GLM_API_KEY",
]

for var in env_vars:
    value = os.getenv(var, "(未设置)")
    if "KEY" in var and value and value != "(未设置)":
        value = f"{value[:8]}...{value[-4:]}"
    print(f"  {var:<20} {value}")

print(f"\n{'=' * 80}")
print("✅ 验证完成")
print("=" * 80)
