"""调试尺寸配置"""
import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

print("=" * 60)
print("环境变量检查")
print("=" * 60)
print(f"COGVIEW_SIZE: '{os.getenv('COGVIEW_SIZE', '未设置')}'")
print(f"IMAGE_PROVIDER: '{os.getenv('IMAGE_PROVIDER', '未设置')}'")
print(f"IMAGE_MODEL: '{os.getenv('IMAGE_MODEL', '未设置')}'")

# 模拟 get_image_config() 逻辑
provider = (os.getenv("IMAGE_PROVIDER") or "seedream").strip().lower()
print(f"\n解析后的 provider: '{provider}'")

_default_size = "2K" if provider == "seedream" else "1024x1024"
print(f"_default_size: '{_default_size}'")

size = os.getenv("COGVIEW_SIZE", _default_size)
print(f"最终 size: '{size}'")

# 实际调用 get_image_config()
print("\n" + "=" * 60)
print("实际调用 get_image_config()")
print("=" * 60)
from app.config.model_config import get_image_config

config = get_image_config()
print(f"config.size: '{config.size}'")
print(f"config.provider: '{config.provider}'")
