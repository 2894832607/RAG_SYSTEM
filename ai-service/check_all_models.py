"""
全链路模型 API Key 诊断工具

检查所有模型调用链路的配置正确性：
1. LLM (文本生成) - GLM/Doubao/Ollama/Qwen
2. Image (图像生成) - CogView/Seedream/LocalSDXL
3. Video (视频生成) - Seedance/Vidu/CogVideoX
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# 加载 .env.local 文件
env_path = Path(__file__).parent / ".env.local"
if env_path.exists():
    load_dotenv(env_path)
    print(f"✅ 已加载环境变量：{env_path.absolute()}\n")
else:
    print(f"⚠️  未找到 .env.local 文件：{env_path.absolute()}\n")

from app.config.model_config import (
    get_llm_config,
    get_image_config,
    get_video_config,
    _PROVIDER_PRESETS,
    _VALID_LLM_PROVIDERS,
    _VALID_IMAGE_PROVIDERS,
    _VALID_VIDEO_PROVIDERS,
)


def mask_key(key: str) -> str:
    """API Key 脱敏显示"""
    if not key:
        return "*** NOT SET ***"
    return key[:8] + "..." if len(key) > 8 else key[:4] + "..."


def check_llm_chain():
    """检查 LLM 链路"""
    print("=" * 80)
    print("📝 LLM (文本生成) 链路检查")
    print("=" * 80)
    
    config = get_llm_config()
    
    print(f"Provider:     {config.provider}")
    print(f"Model:        {config.model}")
    print(f"Base URL:     {config.base_url}")
    print(f"API Key:      {mask_key(config.api_key)}")
    print(f"Temperature:  {config.temperature}")
    print(f"Timeout:      {config.timeout}")
    
    # 验证
    issues = []
    if not config.api_key and config.provider != "ollama":
        issues.append("❌ API Key 未配置")
    if config.provider not in _VALID_LLM_PROVIDERS:
        issues.append(f"❌ Provider 无效：{config.provider}")
    if not config.base_url:
        issues.append("❌ Base URL 未配置")
    
    if issues:
        print("\n发现问题:")
        for issue in issues:
            print(f"  {issue}")
        return False
    else:
        print("\n✅ LLM 链路配置正常")
        return True


def check_image_chain():
    """检查图像生成链路"""
    print("\n" + "=" * 80)
    print("🎨 Image (图像生成) 链路检查")
    print("=" * 80)
    
    config = get_image_config()
    
    print(f"Provider:     {config.provider}")
    print(f"Model:        {config.model}")
    print(f"Base URL:     {config.base_url}")
    print(f"API Key:      {mask_key(config.api_key)}")
    print(f"Size:         {config.size}")
    print(f"Timeout:      {config.timeout}")
    
    # 验证
    issues = []
    if config.provider == "disabled":
        print("\n⚠️  图像生成已禁用")
        return True
    
    if config.provider not in _VALID_IMAGE_PROVIDERS:
        issues.append(f"❌ Provider 无效：{config.provider}")
    
    # 不同 provider 的验证规则
    if config.provider == "local_sdxl":
        if not config.base_url.startswith("http"):
            issues.append("❌ Local SDXL URL 无效")
    elif config.provider in ["seedream", "cogview", "zhipu"]:
        if not config.api_key:
            issues.append("❌ API Key 未配置")
        if not config.base_url:
            issues.append("❌ Base URL 未配置")
    
    if issues:
        print("\n发现问题:")
        for issue in issues:
            print(f"  {issue}")
        return False
    else:
        print("\n✅ 图像生成链路配置正常")
        return True


def check_video_chain():
    """检查视频生成链路"""
    print("\n" + "=" * 80)
    print("🎬 Video (视频生成) 链路检查")
    print("=" * 80)
    
    config = get_video_config()
    
    print(f"Provider:       {config.provider}")
    print(f"Model:          {config.model}")
    print(f"Base URL:       {config.base_url}")
    print(f"API Key:        {mask_key(config.api_key)}")
    print(f"Timeout:        {config.timeout}s")
    print(f"Poll Interval:  {config.poll_interval}s")
    
    # 验证
    issues = []
    if config.provider == "disabled":
        print("\n⚠️  视频生成已禁用")
        return True
    
    if config.provider not in _VALID_VIDEO_PROVIDERS:
        issues.append(f"❌ Provider 无效：{config.provider}")
    
    if config.provider in ["seedance", "vidu", "zhipu"]:
        if not config.api_key:
            issues.append("❌ API Key 未配置")
        if not config.base_url:
            issues.append("❌ Base URL 未配置")
    
    if issues:
        print("\n发现问题:")
        for issue in issues:
            print(f"  {issue}")
        return False
    else:
        print("\n✅ 视频生成链路配置正常")
        return True


def check_env_consistency():
    """检查环境变量一致性"""
    print("\n" + "=" * 80)
    print("🔗 环境变量一致性检查")
    print("=" * 80)
    
    env_vars = {
        "LLM_API_KEY": os.getenv("LLM_API_KEY"),
        "LLM_BASE_URL": os.getenv("LLM_BASE_URL"),
        "LLM_MODEL": os.getenv("LLM_MODEL"),
        "IMAGE_API_KEY": os.getenv("IMAGE_API_KEY"),
        "IMAGE_BASE_URL": os.getenv("IMAGE_BASE_URL"),
        "IMAGE_MODEL": os.getenv("IMAGE_MODEL"),
        "IMAGE_PROVIDER": os.getenv("IMAGE_PROVIDER"),
        "VIDEO_API_KEY": os.getenv("VIDEO_API_KEY"),
        "VIDEO_BASE_URL": os.getenv("VIDEO_BASE_URL"),
        "VIDEO_MODEL": os.getenv("VIDEO_MODEL"),
        "VIDEO_PROVIDER": os.getenv("VIDEO_PROVIDER"),
    }
    
    print("\n环境变量值:")
    for key, value in env_vars.items():
        if value:
            if "KEY" in key:
                print(f"  {key}: {mask_key(value)}")
            else:
                print(f"  {key}: {value}")
        else:
            print(f"  {key}: *** NOT SET ***")
    
    # 检查潜在问题
    issues = []
    
    # 检查豆包相关配置
    image_provider = os.getenv("IMAGE_PROVIDER", "").lower()
    if image_provider == "seedream":
        image_key = os.getenv("IMAGE_API_KEY")
        llm_key = os.getenv("LLM_API_KEY")
        if not image_key and llm_key:
            print("\n⚠️  警告：IMAGE_API_KEY 未设置，将回退使用 LLM_API_KEY")
            print(f"   LLM_API_KEY 前缀：{mask_key(llm_key)}")
            if "bigmodel" in os.getenv("LLM_BASE_URL", ""):
                print("   ⚠️  LLM_BASE_URL 指向智谱 GLM，可能不适用于豆包图像生成")
    
    # 检查视频配置
    video_provider = os.getenv("VIDEO_PROVIDER", "").lower()
    if video_provider == "seedance":
        video_key = os.getenv("VIDEO_API_KEY")
        image_key = os.getenv("IMAGE_API_KEY")
        if not video_key and not image_key:
            print("\n⚠️  警告：VIDEO_API_KEY 和 IMAGE_API_KEY 均未设置")
            print("   视频生成将回退使用 LLM_API_KEY")
    
    if issues:
        print("\n发现问题:")
        for issue in issues:
            print(f"  {issue}")
        return False
    else:
        print("\n✅ 环境变量一致性检查通过")
        return True


def main():
    """主诊断函数"""
    print("=" * 80)
    print("🔍 全链路模型 API Key 诊断")
    print("=" * 80)
    print()
    
    results = {
        "LLM": check_llm_chain(),
        "Image": check_image_chain(),
        "Video": check_video_chain(),
        "Env": check_env_consistency(),
    }
    
    print("\n" + "=" * 80)
    print("📊 诊断总结")
    print("=" * 80)
    
    for chain, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {chain}: {status}")
    
    all_passed = all(results.values())
    
    print("\n" + "=" * 80)
    if all_passed:
        print("✅ 所有链路配置正常！")
    else:
        print("❌ 部分链路配置存在问题，请根据上述提示修复")
    print("=" * 80)
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
