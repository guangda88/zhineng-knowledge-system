"""本地嵌入服务

使用 BGE-M3 模型提供文本嵌入向量生成服务
支持中文和多语言文本
"""

import logging
import os
from pathlib import Path
from typing import List

import torch
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

model = None
model_load_error = None

REQUIRED_MODEL_FILES = ["config.json", "modules.json"]


class EmbedRequest(BaseModel):
    text: str
    normalize: bool = True


class EmbedBatchRequest(BaseModel):
    texts: List[str]
    normalize: bool = True


class EmbedResponse(BaseModel):
    embedding: List[float]
    dim: int


class EmbedBatchResponse(BaseModel):
    embeddings: List[List[float]]
    dim: int


app = FastAPI(
    title="BGE-M3 Embedding Service", description="基于 BGE-M3 的文本嵌入服务", version="1.0.0"
)


def _validate_model_path(model_path: str) -> str:
    model_dir = Path(model_path)
    if not model_dir.is_dir():
        raise FileNotFoundError(f"模型目录不存在: {model_path}")

    missing = [f for f in REQUIRED_MODEL_FILES if not (model_dir / f).exists()]
    if missing:
        raise FileNotFoundError(f"模型文件缺失: {missing} (路径: {model_path})")

    safetensors = list(model_dir.glob("*.safetensors"))
    bin_files = list(model_dir.glob("pytorch_model*.bin"))
    if not safetensors and not bin_files:
        raise FileNotFoundError(
            f"模型权重文件缺失 (*.safetensors 或 pytorch_model*.bin), 路径: {model_path}"
        )

    total_size = sum(f.stat().st_size for f in model_dir.rglob("*") if f.is_file())
    total_mb = total_size / (1024 * 1024)
    logger.info(f"模型目录: {model_path}, 总大小: {total_mb:.1f}MB")
    if total_mb < 100:
        raise ValueError(f"模型文件过小 ({total_mb:.1f}MB), 可能不完整 (BGE-M3 应约 2200MB)")

    return str(model_dir.resolve())


@app.on_event("startup")
async def load_model():
    global model, model_load_error
    model_name = os.getenv("EMBEDDING_MODEL", "BAAI/bge-m3")
    device = "cuda" if torch.cuda.is_available() else "cpu"

    logger.info(f"加载模型: {model_name} (设备: {device})")
    try:
        if os.path.isdir(model_name):
            validated_path = _validate_model_path(model_name)
            logger.info(f"本地模型验证通过: {validated_path}")
            model_name = validated_path

        model = SentenceTransformer(model_name, device=device)
        logger.info(f"模型加载成功，向量维度: {model.get_sentence_embedding_dimension()}")
        model_load_error = None
    except Exception as e:
        model_load_error = str(e)
        logger.error(f"模型加载失败: {e}")
        raise


@app.get("/health")
async def health_check():
    status = "healthy" if model is not None else "unhealthy"
    return {
        "status": status,
        "model_loaded": model is not None,
        "model_error": model_load_error,
        "device": "cuda" if torch.cuda.is_available() else "cpu",
    }


@app.get("/info")
async def model_info():
    if model is None:
        raise HTTPException(status_code=503, detail=f"模型未加载: {model_load_error}")

    return {
        "model_name": os.getenv("EMBEDDING_MODEL", "BAAI/bge-m3"),
        "dimension": model.get_sentence_embedding_dimension(),
        "device": "cuda" if torch.cuda.is_available() else "cpu",
        "max_seq_length": model.max_seq_length if hasattr(model, "max_seq_length") else None,
    }


@app.post("/embed", response_model=EmbedResponse)
async def embed_text(request: EmbedRequest):
    if model is None:
        raise HTTPException(status_code=503, detail=f"模型未加载: {model_load_error}")

    try:
        embedding = model.encode(request.text, normalize=request.normalize, show_progress_bar=False)
        embedding_list = embedding.tolist()
        return EmbedResponse(embedding=embedding_list, dim=len(embedding_list))
    except Exception as e:
        logger.error(f"生成嵌入失败: {e}")
        raise HTTPException(status_code=500, detail=f"生成嵌入失败: {str(e)}")


@app.post("/embed_batch", response_model=EmbedBatchResponse)
async def embed_batch(request: EmbedBatchRequest):
    if model is None:
        raise HTTPException(status_code=503, detail=f"模型未加载: {model_load_error}")

    if not request.texts:
        raise HTTPException(status_code=400, detail="文本列表不能为空")

    try:
        embeddings = model.encode(
            request.texts, normalize=request.normalize, show_progress_bar=False
        )
        embeddings_list = [emb.tolist() for emb in embeddings]
        return EmbedBatchResponse(
            embeddings=embeddings_list, dim=len(embeddings_list[0]) if embeddings_list else 0
        )
    except Exception as e:
        logger.error(f"批量生成嵌入失败: {e}")
        raise HTTPException(status_code=500, detail=f"批量生成嵌入失败: {str(e)}")


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("EMBEDDING_SERVICE_PORT", 8001))
    uvicorn.run(app, host="0.0.0.0", port=port)
