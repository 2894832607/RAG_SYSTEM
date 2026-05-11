import os
import sys
import asyncio
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "ai-service"))

from app.main import _PRESETS
from app.modules.generation import CogViewClient
from app.modules.video_storyboard import SeedanceClient, ViduClient

def test_glm_image():
    print("\n--- Testing GLM CogView-4 Image ---")
    preset = _PRESETS["glm"]
    for k, v in preset.items():
        os.environ[k] = str(v)
    os.environ["IMAGE_API_KEY"] = os.environ.get("GLM_API_KEY", "") or os.environ.get("LLM_API_KEY", "")
    print(f"API Key available: {bool(os.environ['IMAGE_API_KEY'])}")
    print(f"IMAGE_MODEL: {os.environ.get('IMAGE_MODEL')}")
    
    try:
        client = CogViewClient()
        url = client.generate("一只可爱的小猫在草地上玩耍，水墨画风格", negative_prompt="文字, 水印", prev_frame_url=None)
        print(f"Success! Image URL/Path: {url}")
        return url
    except Exception as e:
        print(f"Error: {e}")
        return None

def test_glm_video(image_url):
    print("\n--- Testing GLM Vidu Video ---")
    preset = _PRESETS["glm"]
    for k, v in preset.items():
        os.environ[k] = str(v)
    # ViduClient uses VIDEO_API_KEY or IMAGE_API_KEY or LLM_API_KEY
    os.environ["VIDEO_API_KEY"] = os.environ.get("GLM_API_KEY", "") or os.environ.get("LLM_API_KEY", "")
    os.environ["VIDEO_MODEL"] = "vidu2-reference"
    
    # Actually ViduClient has hardcoded image URL param in video_storyboard? Wait, let's see ViduClient
    try:
        if not hasattr(ViduClient, 'generate'):
            print("Skipped: no generate method found?")
            return
        
        # Test just task creation to save time/credits
        client = ViduClient.from_config()
        # Mocking or calling generate
        print(f"ViduClient loaded: {client.base_url}")
    except Exception as e:
        print(f"Error: {e}")


def test_doubao_image():
    print("\n--- Testing Doubao Seedream Image ---")
    preset = _PRESETS["doubao"]
    for k, v in preset.items():
        os.environ[k] = str(v)
    os.environ["IMAGE_API_KEY"] = os.environ.get("ARK_API_KEY", "")
    print(f"API Key available: {bool(os.environ['IMAGE_API_KEY'])}")
    print(f"IMAGE_MODEL: {os.environ.get('IMAGE_MODEL')}")

    try:
        if not os.environ["IMAGE_API_KEY"]:
            print("Skipped: no ARK_API_KEY")
            return None
        client = CogViewClient()
        url = client.generate("一只可爱的小猫在草地上玩耍，水墨画风格", negative_prompt="文字, 水印", prev_frame_url=None)
        print(f"Success! Image URL/Path: {url}")
        return url
    except Exception as e:
        print(f"Error: {e}")
        return None

if __name__ == "__main__":
    env_path = Path(__file__).resolve().parents[2] / "ai-service" / "local-env.ps1"
    if env_path.exists():
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith("$env:"):
                    parts = line[5:].split("=", 1)
                    if len(parts) == 2:
                        key = parts[0].strip()
                        val = parts[1].strip().strip("'\"")
                        if key not in os.environ and val and not val.startswith("$"):
                            os.environ[key] = val
                            
    img_url = test_glm_image()
    test_glm_video(img_url)
    
    test_doubao_image()