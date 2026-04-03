# 免费API Key配置清单

**目标**: 配置所有已申请的免费API Key到灵知系统

---

## 📋 需要配置的API Key列表

### ✅ 永久免费（每月重置）

| Provider | 环境变量名 | 当前状态 | 免费额度 |
|----------|-----------|---------|---------|
| GLM（智谱） | `GLM_API_KEY` | ⚠️ 未配置 | 100万tokens/月 |
| 千帆（百度） | `QWEN_API_KEY` | ⚠️ 占位符 | 100万tokens/月 |
| 通义千问（阿里） | `QWEN_DASHSCOPE_API_KEY` | ⚠️ 未配置 | 100万tokens/月 |
| 360智脑 | `ZHIHU_API_KEY` | ⚠️ 未配置 | 100万tokens/月 |
| 讯飞星火 | `SPARK_API_KEY` | ⚠️ 未配置 | 50万tokens/月 |

### 🎁 新用户试用

| Provider | 环境变量名 | 当前状态 | 免费额度 | 有效期 |
|----------|-----------|---------|---------|--------|
| DeepSeek | `DEEPSEEK_API_KEY` | ✅ 已配置 | 500万tokens | 30天 |
| 混元（腾讯） | `HUNYUAN_API_KEY` | ⚠️ 未配置 | 100万tokens | 30天 |
| 豆包（字节） | `DOUBAO_API_KEY` | ⚠️ 未配置 | 200万tokens | 30天 |
| Kimi（月之暗面） | `MOONSHOT_API_KEY` | ⚠️ 未配置 | 300万tokens | 30天 |
| Minimax | `MINIMAX_API_KEY` | ⚠️ 未配置 | 100万tokens | 60天 |

---

## 🎯 配置步骤

### 步骤1: 准备您的API Key

请将您申请到的所有API Key整理成如下格式：

```
GLM_API_KEY=您申请的GLM密钥
QWEN_API_KEY=您申请的千帆密钥
QWEN_DASHSCOPE_API_KEY=您申请的通义千问密钥
ZHIHU_API_KEY=您申请的360智脑密钥
SPARK_API_KEY=您申请的讯飞星火密钥
HUNYUAN_API_KEY=您申请的混元密钥
DOUBAO_API_KEY=您申请的豆包密钥
MOONSHOT_API_KEY=您申请的Kimi密钥
MINIMAX_API_KEY=您申请的Minimax密钥
```

### 步骤2: 编辑.env文件

```bash
# 打开配置文件
nano .env

# 找到并替换以下占位符：
QWEN_API_KEY=your_qwen_api_key_here         → 替换为您的千帆密钥
GLM_API_KEY=your_glm_api_key_here           → 替换为您的GLM密钥
QWEN_DASHSCOPE_API_KEY=your_dashscope_key   → 替换为您的通义密钥
ZHIHU_API_KEY=your_zhihu_api_key_here       → 替换为您的360密钥
SPARK_API_KEY=your_spark_api_key_here       → 替换为您的讯飞密钥
HUNYUAN_API_KEY=your_hunyuan_api_key_here   → 替换为您的混元密钥
DOUBAO_API_KEY=your_doubao_api_key_here     → 替换为您的豆包密钥
MOONSHOT_API_KEY=your_moonshot_api_key_here → 替换为您的Kimi密钥
MINIMAX_API_KEY=your_minimax_api_key_here   → 替换为您的Minimax密钥

# 保存退出：Ctrl+X → Y → Enter
```

### 步骤3: 验证配置

```bash
# 运行完整测试
python scripts/test_free_token_pool.py

# 应该看到多个 ✅ 成功
```

---

## 📊 配置完成后可获得

### 最小配置（P0 必配）

```
✅ GLM + 千帆 + 通义千问
总额度: 300万tokens/月
价值: ¥465/月
```

### 推荐配置（P0+P1）

```
✅ GLM + 千帆 + 通义 + DeepSeek + 混元
永久: 300万tokens/月
试用: 600万tokens (30天)
总价值: ¥630
```

### 完整配置（全部）

```
✅ 全部10个provider
永久: 450万tokens/月
试用: 1200万tokens (30-60天)
总价值: ¥1,385
```

---

## 🔑 API Key格式参考

| Provider | 密钥格式示例 |
|----------|-------------|
| GLM | 以 `id-` 或 `glm-` 开头 |
| 千帆 | 以 `ak-` 开头 |
| 通义千问 | 以 `sk-` 开头，24位字符 |
| 360智脑 | 通常是32位字符串 |
| 讯飞星火 | 通常是32位字符串 |
| DeepSeek | 以 `sk-` 开头 |
| 混元 | 以 `sk-` 开头 |
| 豆包 | 通常是ak/sk对 |
| Kimi | 以 `sk-` 开头 |
| Minimax | 通常是自定义格式 |

---

## ⚠️ 注意事项

1. **不要提交到git**: .env文件已在.gitignore中
2. **保密**: API Key等同于密码，请妥善保管
3. **定期检查**: 免费额度使用情况可在各平台控制台查看
4. **试用期限**: 新用户额度会在30-60天后到期，到期后只保留永久免费额度

---

## 🚀 下一步

配置完成后运行：

```bash
# 测试所有API Key
python scripts/test_free_token_pool.py

# 查看Token池状态
python -c "
import asyncio
from backend.services.evolution.free_token_pool import get_free_token_pool

async def check():
    pool = get_free_token_pool()
    status = pool.get_pool_status()
    print(f'总额度: {status[\"total_quota\"]:,} tokens')
    print(f'已使用: {status[\"total_used\"]:,} tokens')
    print(f'剩余: {status[\"total_remaining\"]:,} tokens')
    print(f'\n可用providers:')
    for name, info in status['providers'].items():
        if info['available']:
            print(f'  ✅ {name}: {info[\"remaining\"]:,} tokens')

asyncio.run(check())
"
```
