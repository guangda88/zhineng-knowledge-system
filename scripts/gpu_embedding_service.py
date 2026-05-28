#!/usr/bin/env python3
"""
Host GPU embedding service — FastAPI on CUDA.
Runs on zhineng-ai host (GTX 1660 Ti), ~2100 texts/s.
Port 8010 to avoid conflict with Docker embedding (8001).
"""

import os
import time
import torch
import numpy as np
from fastapi import FastAPI
from pydantic import BaseModel
from typing import List, Optional
from contextlib import asynccontextmanager

os.environ.setdefault("TRANSFORMERS_ATTN_IMPLEMENTATION", "eager")
os.environ.setdefault("PYTORCH_NO_CUDA_MEMORY_CACHING", "1")

MODEL_PATH = os.getenv("EMBEDDING_MODEL", "/data/models/bge-small-zh")
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

model = None


def _patch_bert_attention():
    import transformers.models.bert.modeling_bert as bert_mod
    torch.backends.cuda.enable_flash_sdp(False)
    torch.backends.cuda.enable_mem_efficient_sdp(False)
    _orig = bert_mod.BertSelfAttention.forward

    def _patched(self, hidden_states, attention_mask=None, head_mask=None,
                 encoder_hidden_states=None, encoder_attention_mask=None,
                 past_key_value=None, output_attentions=False):
        with torch.backends.cuda.sdp_kernel(enable_flash=False, enable_mem_efficient=False, enable_math=True):
            return _orig(self, hidden_states, attention_mask, head_mask,
                         encoder_hidden_states, encoder_attention_mask,
                         past_key_value, output_attentions)

    bert_mod.BertSelfAttention.forward = _patched


@asynccontextmanager
async def lifespan(app):
    global model
    from sentence_transformers import SentenceTransformer
    if DEVICE == "cuda":
        _patch_bert_attention()
    model = SentenceTransformer(MODEL_PATH).to(DEVICE)
    dim = model.get_sentence_embedding_dimension()
    print(f"GPU Embedding Service: device={DEVICE}, model={MODEL_PATH}, dim={dim}", flush=True)
    yield
    del model
    if DEVICE == "cuda":
        torch.cuda.empty_cache()


app = FastAPI(title="LingZhi GPU Embedding Service", lifespan=lifespan)


class EmbedRequest(BaseModel):
    texts: List[str]
    normalize: bool = True
    batch_size: int = 64


class EmbedResponse(BaseModel):
    embeddings: List[List[float]]
    dim: int
    count: int
    elapsed_ms: float


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "device": DEVICE,
        "gpu": torch.cuda.get_device_name(0) if DEVICE == "cuda" else None,
        "model": MODEL_PATH,
    }


@app.post("/embed", response_model=EmbedResponse)
async def embed(req: EmbedRequest):
    t0 = time.time()
    embeddings = model.encode(
        req.texts,
        batch_size=req.batch_size,
        normalize_embeddings=req.normalize,
        show_progress_bar=False,
    )
    elapsed = (time.time() - t0) * 1000
    return EmbedResponse(
        embeddings=embeddings.tolist(),
        dim=embeddings.shape[1],
        count=len(req.texts),
        elapsed_ms=round(elapsed, 1),
    )


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("GPU_EMBEDDING_PORT", "8010"))
    uvicorn.run(app, host="0.0.0.0", port=port)
