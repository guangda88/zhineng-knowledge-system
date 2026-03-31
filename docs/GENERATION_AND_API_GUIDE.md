# 灵知系统 - 内容生成与外部API指南

**版本**: 1.0.0
**日期**: 2026-03-31
**适用**: 开发者和系统集成人员

---

## 📚 目录

1. [概述](#概述)
2. [内容生成能力](#内容生成能力)
3. [外部API接口](#外部api接口)
4. [人机交互标注系统](#人机交互标注系统)
5. [最佳实践](#最佳实践)

---

## 概述

灵知系统提供强大的内容生成能力和标准化的外部API接口，支持：

### 🎨 内容生成
- **报告生成**: 学术报告、研究综述、课程笔记、实践总结
- **PPT生成**: 课程演示、学术汇报、培训材料
- **音频生成**: TTS文字转语音
- **视频生成**: 教学视频、专题讲解
- **课程生成**: 完整课程结构与内容
- **数据分析**: 知识图谱分析、学习进度分析

### 🔌 外部API
- 标准化REST API
- API密钥认证
- 速率限制保护
- 完善的权限管理

### ✅ 人机交互标注
- OCR文本标注
- 语音转写标注
- 持续优化识别精度

---

## 内容生成能力

### 1. 报告生成

**功能**：自动生成各类知识报告

**支持的报告类型**：
- `academic` - 学术报告
- `review` - 研究综述
- `notes` - 课程笔记
- `practice` - 实践总结
- `analysis` - 专题分析

**API示例**：

```bash
curl -X POST "http://localhost:8000/api/v1/generation/report" \
  -H "Content-Type: application/json" \
  -d '{
      "topic": "混元气理论",
      "report_type": "academic",
      "sections": ["引言", "理论基础", "实践应用", "总结"],
      "include_references": true,
      "language": "zh",
      "output_format": "md"
  }'
```

**返回结果**：

```json
{
  "task_id": "report_20260331_143052_a1b2c3d4",
  "status": "started",
  "message": "报告生成任务已启动: 混元气理论"
}
```

**查询进度**：

```bash
curl "http://localhost:8000/api/v1/generation/status/report_20260331_143052_a1b2c3d4"
```

### 2. PPT生成

**功能**：自动生成演示文稿

**参数**：
- `topic`: 演示主题
- `slide_count`: 幻灯片数量（1-100）
- `style`: 风格（academic, teaching, presentation）
- `theme`: 主题（default, minimal, colorful）

**API示例**：

```bash
curl -X POST "http://localhost:8000/api/v1/generation/ppt" \
  -H "Content-Type: application/json" \
  -d '{
      "topic": "智能气功基础理论",
      "slide_count": 15,
      "style": "teaching",
      "theme": "default",
      "language": "zh"
  }'
```

### 3. 音频生成（TTS）

**功能**：将文字转换为语音

**参数**：
- `text`: 要转换的文本
- `voice`: 音色（default, female, male）
- `speed`: 语速（0.5-2.0）
- `output_format`: 输出格式（mp3, wav, ogg）

**API示例**：

```bash
curl -X POST "http://localhost:8000/api/v1/generation/audio" \
  -H "Content-Type: application/json" \
  -d '{
      "text": "欢迎来到灵知知识系统。混元气是智能气功的核心概念。",
      "voice": "female",
      "speed": 1.0,
      "output_format": "mp3"
  }'
```

### 4. 视频生成

**功能**：生成教学视频

**参数**：
- `topic`: 视频主题
- `duration`: 视频时长（秒）
- `style`: 视频风格（educational, documentary, tutorial）
- `include_subtitles`: 是否包含字幕

**API示例**：

```bash
curl -X POST "http://localhost:8000/api/v1/generation/video" \
  -H "Content-Type: application/json" \
  -d '{
      "topic": "三心并站庄练习方法",
      "duration": 300,
      "style": "educational",
      "include_subtitles": true
  }'
```

### 5. 课程生成

**功能**：自动生成完整课程

**参数**：
- `title`: 课程标题
- `target_audience`: 目标受众
- `duration_weeks`: 课程周数
- `chapters`: 自定义章节（可选）
- `include_exercises`: 是否包含练习

**API示例**：

```bash
curl -X POST "http://localhost:8000/api/v1/generation/course" \
  -H "Content-Type: application/json" \
  -d '{
      "title": "智能气功入门",
      "target_audience": "初学者",
      "duration_weeks": 8,
      "include_exercises": true
  }'
```

### 6. 数据分析

**功能**：对知识库进行多维度分析

**支持的分析类型**：
- `knowledge_graph` - 知识图谱分析
- `learning_progress` - 学习进度分析
- `content_distribution` - 内容分布分析
- `user_behavior` - 用户行为分析

**API示例**：

```bash
curl -X POST "http://localhost:8000/api/v1/generation/analyze" \
  -H "Content-Type: application/json" \
  -d '{
      "analysis_type": "knowledge_graph",
      "parameters": {}
  }'
```

**返回结果**：

```json
{
  "analysis_type": "knowledge_graph",
  "result": {
    "nodes_count": 1250,
    "edges_count": 3420,
    "clusters": [
      {"name": "智能气功", "size": 320},
      {"name": "中医基础", "size": 280}
    ],
    "most_connected_nodes": [
      {"name": "混元气", "connections": 45},
      {"name": "意元体", "connections": 38}
    ]
  }
}
```

---

## 外部API接口

### 认证方式

使用API密钥进行认证：

```bash
curl -X POST "http://localhost:8000/api/v1/external/v1/search" \
  -H "X-API-Key: your_api_key_here" \
  -H "Content-Type: application/json" \
  -d '{"query": "混元气"}'
```

### 1. 搜索知识库

**端点**: `POST /external/v1/search`

**权限**: `search`

**参数**：
- `query`: 搜索查询（必填）
- `category`: 知识分类（可选）
- `limit`: 返回数量（1-100，默认10）
- `threshold`: 相似度阈值（0.0-1.0，默认0.5）

**示例**：

```bash
curl -X POST "http://localhost:8000/api/v1/external/v1/search" \
  -H "X-API-Key: lingzhi_dev_key_2026" \
  -H "Content-Type: application/json" \
  -d '{
      "query": "什么是混元气",
      "category": "气",
      "limit": 10,
      "threshold": 0.6
  }'
```

**响应**：

```json
{
  "success": true,
  "message": "找到8条结果",
  "data": {
    "query": "什么是混元气",
    "total": 8,
    "results": [
      {
        "content": "混元气是智能气功的核心概念...",
        "source": "智能气功科学基础",
        "category": "气",
        "score": 0.92,
        "metadata": {"page": 15, "chapter": "第二章"}
      }
    ]
  },
  "timestamp": "2026-03-31T14:30:52"
}
```

### 2. 检索知识

**端点**: `POST /external/v1/retrieve`

**权限**: `retrieve`

**参数**：
- `query`: 检索内容（必填）
- `top_k`: 返回最相关的K个结果（1-50，默认5）
- `filters`: 过滤条件（可选）

**示例**：

```bash
curl -X POST "http://localhost:8000/api/v1/external/v1/retrieve" \
  -H "X-API-Key: lingzhi_dev_key_2026" \
  -H "Content-Type: application/json" \
  -d '{
      "query": "形神合一的理论基础",
      "top_k": 5,
      "filters": {
        "category": "气",
        "min_score": 0.7
      }
  }'
```

### 3. 列出分类

**端点**: `GET /external/v1/categories`

**权限**: `search`

**示例**：

```bash
curl "http://localhost:8000/api/v1/external/v1/categories" \
  -H "X-API-Key: lingzhi_dev_key_2026"
```

**响应**：

```json
{
  "success": true,
  "data": {
    "categories": {
      "儒": {"name": "儒家", "description": "儒家思想典籍", "count": 520},
      "释": {"name": "佛学", "description": "佛学经典与智慧", "count": 480},
      "道": {"name": "道家", "description": "道家文化与修行", "count": 560},
      "医": {"name": "中医", "description": "中医理论与实践", "count": 680},
      "武": {"name": "武术", "description": "武术与传统养生", "count": 320},
      "哲": {"name": "哲学", "description": "哲学思辨与理论", "count": 440},
      "科": {"name": "科学", "description": "科学与现代研究", "count": 280},
      "气": {"name": "气功", "description": "智能气功理论与实践", "count": 720}
    },
    "total": 8
  }
}
```

### 4. 获取统计

**端点**: `GET /external/v1/stats`

**权限**: `analyze`

**示例**：

```bash
curl "http://localhost:8000/api/v1/external/v1/stats" \
  -H "X-API-Key: lingzhi_dev_key_2026"
```

### 5. 分析文本

**端点**: `POST /external/v1/analyze`

**权限**: `analyze`

**支持的分析类型**：
- `sentiment` - 情感分析
- `keywords` - 关键词提取
- `summary` - 摘要生成
- `category` - 分类预测

**示例**：

```bash
curl -X POST "http://localhost:8000/api/v1/external/v1/analyze" \
  -H "X-API-Key: lingzhi_dev_key_2026" \
  -H "Content-Type: application/json" \
  -d '{
      "text": "混元气是智能气功的核心理论，它强调形神合一...",
      "analysis_type": "keywords"
  }'
```

### 6. 健康检查

**端点**: `GET /external/v1/health`

**权限**: 无需认证

**示例**：

```bash
curl "http://localhost:8000/api/v1/external/v1/health"
```

**响应**：

```json
{
  "status": "healthy",
  "service": "Lingzhi External API",
  "version": "1.0.0",
  "timestamp": "2026-03-31T14:30:52"
}
```

---

## 人机交互标注系统

### 概述

标注系统用于提升OCR和语音识别的准确率，通过人工校正持续优化识别效果。

### 1. OCR标注

#### 创建OCR标注任务

**端点**: `POST /annotation/ocr/create`

**请求**：

```bash
curl -X POST "http://localhost:8000/api/v1/annotation/ocr/create" \
  -H "Content-Type: application/json" \
  -d '{
      "text": "这是OCR识别的文本，可能包含错误。",
      "source": "/path/to/document.pdf:page_1",
      "metadata": {
        "page": 1,
        "ocr_engine": "tesseract",
        "confidence": 0.85
      }
  }'
```

#### 提交OCR校正

**端点**: `POST /annotation/ocr/correct`

**请求**：

```bash
curl -X POST "http://localhost:8000/api/v1/annotation/ocr/correct" \
  -H "Content-Type: application/json" \
  -d '{
      "task_id": "ocr_20260331_143052_a1b2c3d4",
      "corrected_text": "这是人工校正后的正确文本。",
      "corrections": [
        {
          "position": 4,
          "original": "识别",
          "corrected": "校正",
          "correction_type": "substitution",
          "confidence": 1.0
        }
      ],
      "annotator": "user_123"
  }'
```

#### 批量OCR标注

**端点**: `POST /annotation/ocr/batch`

**请求**：

```bash
curl -X POST "http://localhost:8000/api/v1/annotation/ocr/batch" \
  -H "Content-Type: application/json" \
  -d '{
      "pdf_path": "/path/to/document.pdf",
      "ocr_engine": "tesseract"
  }'
```

### 2. 语音转写标注

#### 创建转写标注任务

**端点**: `POST /annotation/transcription/create`

**请求**：

```bash
curl -X POST "http://localhost:8000/api/v1/annotation/transcription/create" \
  -H "Content-Type: application/json" \
  -d '{
      "text": "这是语音识别的结果，可能需要校正。",
      "audio_source": "/path/to/audio.mp3",
      "speaker": "speaker_1",
      "timestamp_start": 0.0,
      "timestamp_end": 5.2,
      "confidence": 0.88
  }'
```

#### 提交转写校正

**端点**: `POST /annotation/transcription/correct`

**请求**：

```bash
curl -X POST "http://localhost:8000/api/v1/annotation/transcription/correct" \
  -H "Content-Type: application/json" \
  -d '{
      "task_id": "transcription_20260331_143052_a1b2c3d4",
      "corrected_text": "这是校正后的正确文本。",
      "corrections": [
        {
          "position": 3,
          "original": "语音",
          "corrected": "语言",
          "correction_type": "substitution",
          "confidence": 1.0
        }
      ],
      "annotator": "user_123"
  }'
```

#### 批量转写标注

**端点**: `POST /annotation/transcription/batch`

**请求**：

```bash
curl -X POST "http://localhost:8000/api/v1/annotation/transcription/batch" \
  -H "Content-Type: application/json" \
  -d '{
      "audio_path": "/path/to/lecture.mp3",
      "asr_engine": "whisper",
      "speaker_diarization": true
  }'
```

### 3. 标注统计

**获取OCR统计**：

```bash
curl "http://localhost:8000/api/v1/annotation/ocr/stats"
```

**获取转写统计**：

```bash
curl "http://localhost:8000/api/v1/annotation/transcription/stats"
```

**获取整体统计**：

```bash
curl "http://localhost:8000/api/v1/annotation/stats"
```

---

## 最佳实践

### 1. 内容生成

✅ **推荐做法**：
- 明确指定生成类型和参数
- 使用详细的章节结构生成报告
- 合理设置幻灯片数量（10-30页）
- 定期检查生成进度

❌ **避免**：
- 生成过长的单次内容（超过100页PPT）
- 忽略输出格式要求
- 同时启动过多生成任务

### 2. 外部API使用

✅ **推荐做法**：
- 妥善保管API密钥
- 设置合理的相似度阈值
- 使用缓存减少重复请求
- 处理API错误和限流

❌ **避免**：
- 硬编码API密钥
- 忽略速率限制
- 不处理异常情况

### 3. 标注系统

✅ **推荐做法**：
- 及时完成标注任务
- 提供准确的校正数据
- 记录标注置信度
- 定期查看标注统计

❌ **避免**：
- 提交错误的校正
- 忽略标注质量
- 标注不一致

### 4. 性能优化

**内容生成**：
- 使用后台任务异步生成
- 批量处理相似任务
- 缓存生成模板

**API调用**：
- 使用连接池
- 实现请求重试
- 压缩请求和响应

**标注流程**：
- 优先标注高价值内容
- 使用批量处理
- 定期清理完成任务

---

## 总结

灵知系统提供了完整的内容生成和外部API能力：

✅ **多种生成能力**: 报告、PPT、音频、视频、课程、数据分析
✅ **标准化API**: REST API，支持搜索、检索、分析
✅ **人机交互标注**: OCR和语音转写标注，持续优化精度
✅ **完善的权限管理**: API密钥认证，速率限制保护

这些能力使灵知系统成为一个**强大的知识服务平台**，不仅可以自主学习和进化，还能为外部应用提供知识服务！🌟
