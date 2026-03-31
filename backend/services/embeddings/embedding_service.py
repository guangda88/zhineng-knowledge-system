"""本地嵌入服务

使用 BGE-M3 模型提供文本嵌入向量生成服务
支持中文和多语言文本
"""
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List
import logging
import torch
from sentence_transformers import SentenceTransformer
import os

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 全局模型实例
model = None

# 请求/响应模型
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

# 创建FastAPI应用
app = FastAPI(
    title="BGE-M3 Embedding Service",
    description="基于 BGE-M3 的文本嵌入服务",
    version="1.0.0"
)


@app.on_event("startup")
async def load_model():
    """启动时加载模型"""
    global model
    model_name = os.getenv("EMBEDDING_MODEL", "BAAI/bge-m3")
    device = "cuda" if torch.cuda.is_available() else "cpu"

    logger.info(f"加载模型: {model_name} (设备: {device})")
    try:
        model = SentenceTransformer(model_name, device=device)
        logger.info(f"模型加载成功，向量维度: {model.get_sentence_embedding_dimension()}")
    except Exception as e:
        logger.error(f"模型加载失败: {e}")
        raise


@app.get("/health")
async def health_check():
    """健康检查"""
    return {
        "status": "healthy",
        "model_loaded": model is not None,
        "device": "cuda" if torch.cuda.is_available() else "cpu"
    }


@app.get("/info")
async def model_info():
    """模型信息"""
    if model is None:
        raise HTTPException(status_code=503, detail="模型未加载")

    return {
        "model_name": os.getenv("EMBEDDING_MODEL", "BAAI/bge-m3"),
        "dimension": model.get_sentence_embedding_dimension(),
        "device": "cuda" if torch.cuda.is_available() else "cpu",
        "max_seq_length": model.max_seq_length if hasattr(model, 'max_seq_length') else None
    }


@app.post("/embed", response_model=EmbedResponse)
async def embed_text(request: EmbedRequest):
    """生成单个文本的嵌入向量"""
    if model is None:
        raise HTTPException(status_code=503, detail="模型未加载")

    try:
        # 生成嵌入
        embedding = model.encode(
            request.text,
            normalize=request.normalize,
            show_progress_bar=False
        )
        embedding_list = embedding.tolist()

        return EmbedResponse(
            embedding=embedding_list,
            dim=len(embedding_list)
        )
    except Exception as e:
        logger.error(f"生成嵌入失败: {e}")
        raise HTTPException(status_code=500, detail=f"生成嵌入失败: {str(e)}")


@app.post("/embed_batch", response_model=EmbedBatchResponse)
async def embed_batch(request: EmbedBatchRequest):
    """批量生成文本嵌入向量"""
    if model is None:
        raise HTTPException(status_code=503, detail="模型未加载")

    if not request.texts:
        raise HTTPException(status_code=400, detail="文本列表不能为空")

    try:
        # 批量生成嵌入
        embeddings = model.encode(
            request.texts,
            normalize=request.normalize,
            show_progress_bar=False
        )
        embeddings_list = [emb.tolist() for emb in embeddings]

        return EmbedBatchResponse(
            embeddings=embeddings_list,
            dim=len(embeddings_list[0]) if embeddings_list else 0
        )
    except Exception as e:
        logger.error(f"批量生成嵌入失败: {e}")
        raise HTTPException(status_code=500, detail=f"批量生成嵌入失败: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("EMBEDDING_SERVICE_PORT", 8001))
    uvicorn.run(app, host="0.0.0.0", port=port)
