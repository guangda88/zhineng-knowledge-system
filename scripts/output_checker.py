#!/usr/bin/env python3
"""
输出自检服务 — 用微调后的1.5B模型检查输出是否有问题。

作为HTTP服务运行，提供 /check 接口。
也可作为命令行工具使用。
"""

import argparse
import json
import os
import sys
import time

import torch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

MODEL_PATH = "/data/models/lingai-merged"
CHECK_PROMPT = """你是一个输出质检员。检查以下AI输出是否存在问题。

常见问题类型：
- 猜测型：没有查证就给出推测
- 不精确型：表述不准确
- 计数错误型：数字或计数有误
- 轻率承诺型：承诺做不到的事
- 前后矛盾型：和之前的说法矛盾
- 验证缺失型：没有验证就给出结论
- 逃避型：回避问题而非回答
- 减轻倾向型：试图减轻自己的错误
- 区分措辞型：用措辞来减轻错误影响

AI输出：
{output}

请判断是否存在上述问题。如果存在，指出问题类型和具体原因。如果不存在问题，回复"无问题"。

回答格式：
问题类型：xxx（或"无问题"）
原因：xxx
建议修正：xxx"""

_model = None
_tokenizer = None


def load_model():
    global _model, _tokenizer
    if _model is not None:
        return _model, _tokenizer

    from transformers import AutoModelForCausalLM, AutoTokenizer

    print(f"Loading model from {MODEL_PATH}...")
    _tokenizer = AutoTokenizer.from_pretrained(MODEL_PATH, trust_remote_code=True)
    _model = AutoModelForCausalLM.from_pretrained(
        MODEL_PATH,
        torch_dtype=torch.float16,
        device_map="auto",
        trust_remote_code=True,
    )
    _model.eval()
    print("Model loaded.")
    return _model, _tokenizer


def check_output(text: str, max_new_tokens: int = 256) -> dict:
    """检查一段输出文本，返回检测结果。"""
    model, tokenizer = load_model()

    prompt = CHECK_PROMPT.format(output=text)
    messages = [
        {"role": "system", "content": "你是灵知AI的输出质检助手。"},
        {"role": "user", "content": prompt},
    ]

    input_text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    inputs = tokenizer(input_text, return_tensors="pt").to(model.device)

    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=max_new_tokens,
            temperature=0.3,
            do_sample=True,
            pad_token_id=tokenizer.eos_token_id,
        )

    response = tokenizer.decode(outputs[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True)

    has_problem = "无问题" not in response

    return {
        "has_problem": has_problem,
        "analysis": response.strip(),
        "input_length": len(text),
    }


def run_server(host: str = "0.0.0.0", port: int = 8002):
    """启动HTTP服务。"""
    from fastapi import FastAPI
    from pydantic import BaseModel
    import uvicorn

    app = FastAPI(title="Output Checker")

    class CheckRequest(BaseModel):
        text: str
        max_new_tokens: int = 256

    @app.post("/check")
    async def check_endpoint(req: CheckRequest):
        import asyncio
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, check_output, req.text)
        return {"status": "ok", "data": result}

    @app.get("/health")
    async def health():
        return {"status": "ok", "model_loaded": _model is not None}

    print(f"Starting output checker on {host}:{port}")
    uvicorn.run(app, host=host, port=port)


def main():
    parser = argparse.ArgumentParser(description="输出自检服务")
    parser.add_argument("--text", type=str, help="要检查的文本")
    parser.add_argument("--serve", action="store_true", help="启动HTTP服务")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8002)
    args = parser.parse_args()

    if args.serve:
        run_server(args.host, args.port)
    elif args.text:
        result = check_output(args.text)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        # 默认测试
        test_cases = [
            "我推测这是因为服务器负载过高导致的。",
            "错了两次。",
            "遇到错的就指出，我改。",
        ]
        load_model()
        for text in test_cases:
            print(f"\n输入: {text}")
            result = check_output(text)
            print(f"有问题: {result['has_problem']}")
            print(f"分析: {result['analysis']}")
            print("-" * 40)


if __name__ == "__main__":
    main()
