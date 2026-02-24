import uuid


class DiffusionClient:
    def generate(self, prompt: str) -> str:
        image_name = f"{uuid.uuid4()}.png"
        return f"/statics/outputs/{image_name}"
