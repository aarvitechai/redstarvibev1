"""OpenCLIP image and text embeddings (ViT-B-32, 512 dimensions). Enabled with CLIP_ENABLED and the ai extra."""
import asyncio
import io
from functools import lru_cache

import numpy as np

from app.core.config import settings


@lru_cache
def _model():  # type: ignore[no-untyped-def]
    import open_clip

    model, _, preprocess = open_clip.create_model_and_transforms("ViT-B-32", pretrained="laion2b_s34b_b79k")
    tokenizer = open_clip.get_tokenizer("ViT-B-32")
    model.eval()
    return model, preprocess, tokenizer


def embed_image_sync(data: bytes) -> list[float] | None:
    if not settings.clip_enabled:
        return None
    import torch
    from PIL import Image

    model, preprocess, _ = _model()
    tensor = preprocess(Image.open(io.BytesIO(data)).convert("RGB")).unsqueeze(0)
    with torch.no_grad():
        features = model.encode_image(tensor)
    vec = features[0].numpy()
    return [float(x) for x in vec / np.linalg.norm(vec)]


def _embed_text_sync(text: str) -> list[float]:
    import torch

    model, _, tokenizer = _model()
    with torch.no_grad():
        features = model.encode_text(tokenizer([text]))
    vec = features[0].numpy()
    return [float(x) for x in vec / np.linalg.norm(vec)]


async def embed_image_query(text: str) -> list[float] | None:
    if not settings.clip_enabled:
        return None
    return await asyncio.to_thread(_embed_text_sync, text)
