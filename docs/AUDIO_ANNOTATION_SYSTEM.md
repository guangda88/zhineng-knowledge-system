# 灵知系统 - 音频标注系统设计

**版本**: v1.0.0
**日期**: 2026-03-31
**核心功能**: 音频转写结果的人工标注与校正
**应用场景**: 功法教学、课程录音的质量控制

---

## 🎯 系统定位

### 为什么需要音频标注？

1. **提升转写质量**
   - 纠正ASR错误（专有名词、功法术语）
   - 添加标点符号
   - 优化段落分段

2. **增强内容理解**
   - 标注重点内容
   - 添加教学要点
   - 关联理论知识

3. **支持知识检索**
   - 标注关键词
   - 建立主题索引
   - 关联相关内容

### 应用场景

| 场景 | 标注内容 | 优先级 |
|------|---------|--------|
| **功法教学录音** | 动作要领、注意事项、常见错误 | P0 |
| **理论课程录音** | 重点概念、核心观点、案例说明 | P0 |
| **练习指导录音** | 纠正点、鼓励语、练习建议 | P1 |
| **研讨会议录音** | 议题、结论、行动计划 | P2 |

---

## 📋 标注类型定义

### 1. 基础标注类型

#### 1.1 文本校对 (Text Correction)

**用途**: 纠正ASR转写错误

```python
# 标注示例
{
    "type": "correction",
    "segment_id": 123,
    "original_text": "智能气功混元灵通",
    "corrected_text": "智能气功·混元灵通",
    "reason": "添加间隔号，区分功法名和口诀",
    "corrected_by": "张老师",
    "corrected_at": "2026-03-31T10:00:00Z"
}
```

#### 1.2 段落标注 (Segment Annotation)

**用途**: 标记段落的主题和类型

```python
{
    "type": "segment_label",
    "segment_id": 123,
    "start_time": 125.5,
    "end_time": 180.2,
    "labels": {
        "topic": "三心并站庄",
        "category": "功法教学",
        "level": "入门",
        "keywords": ["站庄", "姿势", "要领"]
    }
}
```

#### 1.3 重点标注 (Highlight)

**用途**: 标记重点内容

```python
{
    "type": "highlight",
    "segment_id": 123,
    "start_time": 150.0,
    "end_time": 165.0,
    "highlight_type": "important",  # important, warning, tip, example
    "color": "#ff5722",
    "note": "这是最关键的姿势要领，需要重点强调"
}
```

### 2. 高级标注类型

#### 2.1 知识点关联 (Knowledge Link)

**用途**: 关联相关理论知识

```python
{
    "type": "knowledge_link",
    "segment_id": 123,
    "start_time": 160.0,
    "end_time": 175.0,
    "links": [
        {
            "type": "theory",
            "title": "混元论",
            "source": "textbook",
            "source_id": "chapter-3-section-2",
            "relevance": 0.95
        },
        {
            "type": "practice",
            "title": "三心并站庄练习方法",
            "source": "practice_guide",
            "source_id": "practice-001"
        }
    ]
}
```

#### 2.2 教学要点 (Teaching Point)

**用途**: 标记教学要点

```python
{
    "type": "teaching_point",
    "segment_id": 123,
    "point_type": "key_point",  # key_point, common_mistake, reminder
    "content": "站庄时要注意膝盖微曲，不要锁死",
    "importance": "high",
    "target_audience": ["初学者", "进阶者"]
}
```

#### 2.3 时间戳笔记 (Timestamp Note)

**用途**: 在特定时间点添加笔记

```python
{
    "type": "timestamp_note",
    "audio_id": 456,
    "timestamp": 167.5,
    "note": "这里可以插入示范视频链接",
    "note_type": "instructional",
    "attachments": [
        {
            "type": "video",
            "url": "https://example.com/demo.mp4",
            "thumbnail": "https://example.com/demo.jpg"
        }
    ]
}
```

---

## 🏗️ 系统架构

```
┌────────────────────────────────────────────────────┐
│               音频标注系统架构                       │
├────────────────────────────────────────────────────┤
│                                                    │
│  ┌──────────────┐      ┌──────────────┐           │
│  │  音频播放器   │─────▶│  波形可视化   │           │
│  │  (带时间轴)   │      │  (标注定点)   │           │
│  └──────────────┘      └──────┬───────┘           │
│         │                      │                    │
│         └──────────┬───────────┘                    │
│                    │                               │
│                    ▼                               │
│         ┌─────────────────────┐                    │
│         │   标注编辑器         │                    │
│         │  - 文本校对          │                    │
│         │  - 重点标记          │                    │
│         │  - 知识关联          │                    │
│         │  - 笔记添加          │                    │
│         └──────────┬──────────┘                    │
│                    │                               │
│                    ▼                               │
│         ┌─────────────────────┐                    │
│         │   标注数据API       │                    │
│         │  - 保存标注          │                    │
│         │  - 查询标注          │                    │
│         │  - 导入导出          │                    │
│         └──────────┬──────────┘                    │
│                    │                               │
│                    ▼                               │
│         ┌─────────────────────┐                    │
│         │  PostgreSQL数据库    │                    │
│         │  - audio_files      │                    │
│         │  - audio_segments   │                    │
│         │  - audio_annotations│                    │
│         └─────────────────────┘                    │
└────────────────────────────────────────────────────┘
```

---

## 📊 数据模型设计

### 扩展数据库表

```sql
-- 音频标注表（主表）
CREATE TABLE audio_annotations (
    id SERIAL PRIMARY KEY,

    -- 关联信息
    audio_file_id INTEGER REFERENCES audio_files(id) ON DELETE CASCADE,
    segment_id INTEGER REFERENCES audio_segments(id) ON DELETE CASCADE,

    -- 标注类型
    annotation_type VARCHAR(50) NOT NULL,
    -- correction, segment_label, highlight, knowledge_link,
    -- teaching_point, timestamp_note

    -- 时间信息
    start_time FLOAT,
    end_time FLOAT,

    -- 标注内容
    content TEXT,
    metadata JSONB NOT NULL DEFAULT '{}',

    -- 示例metadata结构：
    -- {
    --   "correction": {"original": "...", "corrected": "...", "reason": "..."},
    --   "highlight": {"type": "important", "color": "#ff5722"},
    --   "knowledge_link": [{"type": "theory", "source_id": "..."}],
    --   "teaching_point": {"point_type": "key_point", "importance": "high"}
    -- }

    -- 状态
    status VARCHAR(50) DEFAULT 'active',  -- active, deleted, merged

    -- 审核信息
    verified BOOLEAN DEFAULT FALSE,
    verified_by VARCHAR(100),
    verified_at TIMESTAMP,

    -- 创建信息
    created_by VARCHAR(100) NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),

    -- 版本控制
    version INTEGER DEFAULT 1,
    parent_id INTEGER REFERENCES audio_annotations(id)
);

-- 标注标签表
CREATE TABLE annotation_labels (
    id SERIAL PRIMARY KEY,
    label_name VARCHAR(100) NOT NULL UNIQUE,
    label_category VARCHAR(50),  -- topic, level, type, etc.
    color VARCHAR(20),
    description TEXT,
    usage_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW()
);

-- 标注-标签关联表（多对多）
CREATE TABLE annotation_label_relations (
    annotation_id INTEGER REFERENCES audio_annotations(id) ON DELETE CASCADE,
    label_id INTEGER REFERENCES annotation_labels(id) ON DELETE CASCADE,
    PRIMARY KEY (annotation_id, label_id)
);

-- 标注评论表（协作讨论）
CREATE TABLE annotation_comments (
    id SERIAL PRIMARY KEY,
    annotation_id INTEGER REFERENCES audio_annotations(id) ON DELETE CASCADE,
    comment_text TEXT NOT NULL,
    commented_by VARCHAR(100) NOT NULL,
    commented_at TIMESTAMP DEFAULT NOW(),

    -- 回复功能
    parent_comment_id INTEGER REFERENCES annotation_comments(id)
);

-- 标注变更历史（审计）
CREATE TABLE annotation_history (
    id SERIAL PRIMARY KEY,
    annotation_id INTEGER REFERENCES audio_annotations(id) ON DELETE CASCADE,
    action VARCHAR(50) NOT NULL,  -- created, updated, deleted, verified
    old_value JSONB,
    new_value JSONB,
    changed_by VARCHAR(100) NOT NULL,
    changed_at TIMESTAMP DEFAULT NOW()
);

-- 索引
CREATE INDEX idx_annotations_audio ON audio_annotations(audio_file_id);
CREATE INDEX idx_annotations_segment ON audio_annotations(segment_id);
CREATE INDEX idx_annotations_type ON audio_annotations(annotation_type);
CREATE INDEX idx_annotations_time ON audio_annotations(start_time, end_time);
CREATE INDEX idx_annotations_creator ON audio_annotations(created_by);
CREATE INDEX idx_annotations_status ON audio_annotations(status);

-- 全文搜索
CREATE INDEX idx_annotations_content ON audio_annotations USING gin(to_tsvector('chinese', content));
```

---

## 🔧 标注API设计

### 1. 标注CRUD接口

```python
# backend/api/v1/annotations.py
from fastapi import APIRouter, Depends, HTTPException
from typing import List, Optional

router = APIRouter(prefix="/annotations", tags=["annotations"])

# ==================== 创建标注 ====================

@router.post("/")
async def create_annotation(
    audio_file_id: int,
    annotation_type: str,
    segment_id: Optional[int] = None,
    start_time: Optional[float] = None,
    end_time: Optional[float] = None,
    content: Optional[str] = None,
    metadata: dict = None,
    current_user: dict = Depends(get_current_user)
):
    """创建音频标注

    Args:
        audio_file_id: 音频文件ID
        annotation_type: 标注类型
            - correction: 文本校对
            - segment_label: 段落标注
            - highlight: 重点标注
            - knowledge_link: 知识关联
            - teaching_point: 教学要点
            - timestamp_note: 时间戳笔记
        segment_id: 音频分段ID（可选）
        start_time: 开始时间（秒）
        end_time: 结束时间（秒）
        content: 标注内容
        metadata: 元数据（JSON格式）

    Returns:
        创建的标注对象
    """
    # 验证音频文件存在
    audio = await db.get_by_id(audio_files, audio_file_id)
    if not audio:
        raise HTTPException(404, "音频文件不存在")

    # 验证标注类型
    valid_types = [
        "correction", "segment_label", "highlight",
        "knowledge_link", "teaching_point", "timestamp_note"
    ]
    if annotation_type not in valid_types:
        raise HTTPException(400, f"无效的标注类型，必须是: {', '.join(valid_types)}")

    # 验证时间范围
    if start_time is not None and end_time is not None:
        if start_time >= end_time:
            raise HTTPException(400, "start_time必须小于end_time")
        if end_time > audio["duration"]:
            raise HTTPException(400, "end_time超出音频时长")

    # 创建标注
    annotation = await db.insert(audio_annotations, {
        "audio_file_id": audio_file_id,
        "segment_id": segment_id,
        "annotation_type": annotation_type,
        "start_time": start_time,
        "end_time": end_time,
        "content": content,
        "metadata": metadata or {},
        "created_by": current_user["username"]
    })

    # 记录历史
    await db.insert(annotation_history, {
        "annotation_id": annotation["id"],
        "action": "created",
        "new_value": annotation,
        "changed_by": current_user["username"]
    })

    return annotation

# ==================== 查询标注 ====================

@router.get("/audio/{audio_file_id}")
async def get_audio_annotations(
    audio_file_id: int,
    annotation_type: Optional[str] = None,
    start_time: Optional[float] = None,
    end_time: Optional[float] = None,
    include_deleted: bool = False
):
    """获取音频文件的所有标注

    Args:
        audio_file_id: 音频文件ID
        annotation_type: 过滤标注类型（可选）
        start_time: 过滤开始时间（可选）
        end_time: 过滤结束时间（可选）
        include_deleted: 是否包含已删除的标注

    Returns:
        标注列表
    """
    where = {"audio_file_id": audio_file_id}
    if not include_deleted:
        where["status"] = "active"

    if annotation_type:
        where["annotation_type"] = annotation_type

    if start_time is not None and end_time is not None:
        # 时间范围查询
        annotations = await db.query("""
            SELECT * FROM audio_annotations
            WHERE audio_file_id = $1
              AND status = 'active'
              AND annotation_type = $2
              AND (
                  (start_time >= $3 AND start_time <= $4)
                  OR (end_time >= $3 AND end_time <= $4)
                  OR (start_time <= $3 AND end_time >= $4)
              )
            ORDER BY start_time
        """, audio_file_id, annotation_type, start_time, end_time)
    else:
        annotations = await db.select(
            audio_annotations,
            where=where,
            order_by="start_time"
        )

    return annotations

@router.get("/{annotation_id}")
async def get_annotation(annotation_id: int):
    """获取单个标注详情"""
    annotation = await db.get_by_id(audio_annotations, annotation_id)
    if not annotation:
        raise HTTPException(404, "标注不存在")

    # 获取关联的标签
    labels = await db.query("""
        SELECT l.* FROM annotation_labels l
        JOIN annotation_label_relations r ON r.label_id = l.id
        WHERE r.annotation_id = $1
    """, annotation_id)

    # 获取评论
    comments = await db.select(
        annotation_comments,
        where={"annotation_id": annotation_id},
        order_by="commented_at"
    )

    return {
        **annotation,
        "labels": labels,
        "comments": comments
    }

# ==================== 更新标注 ====================

@router.put("/{annotation_id}")
async def update_annotation(
    annotation_id: int,
    content: Optional[str] = None,
    metadata: Optional[dict] = None,
    status: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """更新标注

    Args:
        annotation_id: 标注ID
        content: 新的标注内容
        metadata: 新的元数据
        status: 状态 (active, deleted, merged)

    Returns:
        更新后的标注
    """
    annotation = await db.get_by_id(audio_annotations, annotation_id)
    if not annotation:
        raise HTTPException(404, "标注不存在")

    # 权限检查
    if annotation["created_by"] != current_user["username"]:
        raise HTTPException(403, "无权修改此标注")

    # 保存旧值
    old_value = annotation.copy()

    # 更新
    update_data = {}
    if content is not None:
        update_data["content"] = content
    if metadata is not None:
        update_data["metadata"] = metadata
    if status is not None:
        update_data["status"] = status

    update_data["updated_at"] = datetime.now()

    await db.update(audio_annotations, annotation_id, update_data)

    # 记录历史
    await db.insert(annotation_history, {
        "annotation_id": annotation_id,
        "action": "updated",
        "old_value": old_value,
        "new_value": {**annotation, **update_data},
        "changed_by": current_user["username"]
    })

    return {**annotation, **update_data}

# ==================== 删除标注 ====================

@router.delete("/{annotation_id}")
async def delete_annotation(
    annotation_id: int,
    current_user: dict = Depends(get_current_user)
):
    """删除标注（软删除）"""
    annotation = await db.get_by_id(audio_annotations, annotation_id)
    if not annotation:
        raise HTTPException(404, "标注不存在")

    # 权限检查
    if annotation["created_by"] != current_user["username"]:
        raise HTTPException(403, "无权删除此标注")

    # 软删除
    await db.update(audio_annotations, annotation_id, {
        "status": "deleted",
        "updated_at": datetime.now()
    })

    # 记录历史
    await db.insert(annotation_history, {
        "annotation_id": annotation_id,
        "action": "deleted",
        "old_value": annotation,
        "changed_by": current_user["username"]
    })

    return {"success": True, "message": "标注已删除"}

# ==================== 批量操作 ====================

@router.post("/batch")
async def batch_create_annotations(
    annotations: List[dict],
    current_user: dict = Depends(get_current_user)
):
    """批量创建标注"""
    created = []

    for ann in annotations:
        try:
            created.append(await create_annotation(
                **ann,
                current_user=current_user
            ))
        except Exception as e:
            # 记录错误但继续处理
            print(f"创建标注失败: {e}")

    return {
        "total": len(annotations),
        "created": len(created),
        "annotations": created
    }

@router.delete("/batch")
async def batch_delete_annotations(
    annotation_ids: List[int],
    current_user: dict = Depends(get_current_user)
):
    """批量删除标注"""
    deleted = 0

    for ann_id in annotation_ids:
        try:
            await delete_annotation(ann_id, current_user)
            deleted += 1
        except Exception as e:
            print(f"删除标注失败: {e}")

    return {
        "total": len(annotation_ids),
        "deleted": deleted
    }
```

### 2. 标注评论接口

```python
@router.post("/{annotation_id}/comments")
async def add_comment(
    annotation_id: int,
    comment_text: str,
    parent_comment_id: Optional[int] = None,
    current_user: dict = Depends(get_current_user)
):
    """添加评论"""
    annotation = await db.get_by_id(audio_annotations, annotation_id)
    if not annotation:
        raise HTTPException(404, "标注不存在")

    comment = await db.insert(annotation_comments, {
        "annotation_id": annotation_id,
        "comment_text": comment_text,
        "parent_comment_id": parent_comment_id,
        "commented_by": current_user["username"]
    })

    return comment
```

### 3. 标注导出接口

```python
@router.get("/audio/{audio_file_id}/export")
async def export_annotations(
    audio_file_id: int,
    format: str = "json"  # json, csv, srt
):
    """导出标注

    Args:
        audio_file_id: 音频文件ID
        format: 导出格式

    Returns:
        导出的文件
    """
    annotations = await db.select(
        audio_annotations,
        where={"audio_file_id": audio_file_id, "status": "active"},
        order_by="start_time"
    )

    if format == "json":
        return _export_json(annotations)
    elif format == "csv":
        return _export_csv(annotations)
    elif format == "srt":
        return _export_srt(annotations)
    else:
        raise HTTPException(400, "不支持的格式")

def _export_json(annotations):
    """导出为JSON"""
    return {
        "format": "json",
        "version": "1.0",
        "exported_at": datetime.now().isoformat(),
        "annotations": annotations
    }

def _export_csv(annotations):
    """导出为CSV"""
    import csv
    from io import StringIO

    output = StringIO()
    writer = csv.writer(output)

    # 写入表头
    writer.writerow([
        "ID", "类型", "开始时间", "结束时间", "内容", "创建人", "创建时间"
    ])

    # 写入数据
    for ann in annotations:
        writer.writerow([
            ann["id"],
            ann["annotation_type"],
            ann["start_time"],
            ann["end_time"],
            ann["content"],
            ann["created_by"],
            ann["created_at"]
        ])

    return output.getvalue()
```

---

## 🎨 前端界面设计

### 标注编辑器组件

```javascript
// frontend/components/AnnotationEditor.js
class AnnotationEditor {
    constructor(audioId, options = {}) {
        this.audioId = audioId;
        this.options = options;

        this.audioPlayer = null;
        this.waveform = null;
        this.annotations = [];
        this.selectedAnnotation = null;

        this.init();
    }

    async init() {
        // 1. 加载音频和标注
        await this.loadAudio();
        await this.loadAnnotations();

        // 2. 初始化波形显示
        this.initWaveform();

        // 3. 初始化标注工具栏
        this.initToolbar();

        // 4. 绑定事件
        this.bindEvents();
    }

    async loadAnnotations() {
        const response = await fetch(`/api/v1/annotations/audio/${this.audioId}`);
        this.annotations = await response.json();

        this.renderAnnotations();
    }

    initWaveform() {
        // 使用WaveSurfer.js显示波形
        this.waveform = WaveSurfer.create({
            container: '#waveform',
            waveColor: '#4a90e2',
            progressColor: '#2ecc71',
            cursorColor: '#e74c3c',
            height: 128
        });

        this.waveform.load(this.audioUrl);

        // 标注标记
        this.annotations.forEach(ann => {
            this.waveform.addMarker({
                time: ann.start_time,
                color: this.getAnnotationColor(ann.annotation_type),
                label: ann.annotation_type
            });
        });
    }

    initToolbar() {
        // 标注工具栏
        const toolbar = document.getElementById('annotation-toolbar');
        toolbar.innerHTML = `
            <div class="toolbar-group">
                <button class="btn-highlight" title="重点标注">
                    <i class="fas fa-highlighter"></i> 重点
                </button>
                <button class="btn-correct" title="文字校对">
                    <i class="fas fa-spell-check"></i> 校对
                </button>
                <button class="btn-link" title="知识关联">
                    <i class="fas fa-link"></i> 关联
                </button>
                <button class="btn-note" title="添加笔记">
                    <i class="fas fa-sticky-note"></i> 笔记
                </button>
            </div>
            <div class="toolbar-group">
                <button class="btn-undo" title="撤销">
                    <i class="fas fa-undo"></i>
                </button>
                <button class="btn-redo" title="重做">
                    <i class="fas fa-redo"></i>
                </button>
            </div>
        `;

        // 绑定按钮事件
        toolbar.querySelector('.btn-highlight').addEventListener('click', () => {
            this.createAnnotation('highlight');
        });

        toolbar.querySelector('.btn-correct').addEventListener('click', () => {
            this.createAnnotation('correction');
        });

        toolbar.querySelector('.btn-link').addEventListener('click', () => {
            this.createAnnotation('knowledge_link');
        });

        toolbar.querySelector('.btn-note').addEventListener('click', () => {
            this.createAnnotation('timestamp_note');
        });
    }

    async createAnnotation(type) {
        const currentTime = this.audioPlayer.currentTime();

        // 显示标注对话框
        const dialog = new AnnotationDialog(type, currentTime);
        const result = await dialog.show();

        if (result.confirmed) {
            // 创建标注
            const annotation = await this.saveAnnotation({
                annotation_type: type,
                start_time: result.start_time || currentTime,
                end_time: result.end_time || currentTime + 10,
                content: result.content,
                metadata: result.metadata
            });

            this.annotations.push(annotation);
            this.renderAnnotations();
        }
    }

    async saveAnnotation(data) {
        const response = await fetch('/api/v1/annotations/', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                audio_file_id: this.audioId,
                ...data
            })
        });

        return await response.json();
    }

    renderAnnotations() {
        const container = document.getElementById('annotations-list');
        container.innerHTML = '';

        // 按时间排序
        this.annotations.sort((a, b) => a.start_time - b.start_time);

        // 渲染每个标注
        this.annotations.forEach(ann => {
            const item = document.createElement('div');
            item.className = 'annotation-item';
            item.dataset.id = ann.id;

            item.innerHTML = `
                <div class="annotation-type">
                    ${this.getTypeIcon(ann.annotation_type)}
                    ${this.getTypeName(ann.annotation_type)}
                </div>
                <div class="annotation-time">
                    ${this.formatTime(ann.start_time)} - ${this.formatTime(ann.end_time)}
                </div>
                <div class="annotation-content">
                    ${ann.content || this.renderMetadata(ann.metadata)}
                </div>
                <div class="annotation-actions">
                    <button class="btn-play" title="播放">
                        <i class="fas fa-play"></i>
                    </button>
                    <button class="btn-edit" title="编辑">
                        <i class="fas fa-edit"></i>
                    </button>
                    <button class="btn-delete" title="删除">
                        <i class="fas fa-trash"></i>
                    </button>
                </div>
            `;

            // 播放按钮
            item.querySelector('.btn-play').addEventListener('click', () => {
                this.audioPlayer.seekTo(ann.start_time);
                this.audioPlayer.play();
            });

            // 编辑按钮
            item.querySelector('.btn-edit').addEventListener('click', () => {
                this.editAnnotation(ann);
            });

            // 删除按钮
            item.querySelector('.btn-delete').addEventListener('click', async () => {
                if (confirm('确定删除此标注？')) {
                    await this.deleteAnnotation(ann.id);
                }
            });

            container.appendChild(item);
        });
    }

    getAnnotationColor(type) {
        const colors = {
            'correction': '#ff9800',
            'segment_label': '#2196f3',
            'highlight': '#f44336',
            'knowledge_link': '#4caf50',
            'teaching_point': '#9c27b0',
            'timestamp_note': '#607d8b'
        };
        return colors[type] || '#999';
    }

    getTypeIcon(type) {
        const icons = {
            'correction': '<i class="fas fa-spell-check"></i>',
            'segment_label': '<i class="fas fa-tag"></i>',
            'highlight': '<i class="fas fa-highlighter"></i>',
            'knowledge_link': '<i class="fas fa-link"></i>',
            'teaching_point': '<i class="fas fa-chalkboard-teacher"></i>',
            'timestamp_note': '<i class="fas fa-sticky-note"></i>'
        };
        return icons[type] || '<i class="fas fa-marker"></i>';
    }

    formatTime(seconds) {
        const mins = Math.floor(seconds / 60);
        const secs = Math.floor(seconds % 60);
        return `${mins}:${secs.toString().padStart(2, '0')}`;
    }
}

// 标注对话框
class AnnotationDialog {
    constructor(type, currentTime) {
        this.type = type;
        this.currentTime = currentTime;
        this.dialog = null;
    }

    async show() {
        return new Promise((resolve) => {
            const dialogHtml = `
                <div class="annotation-dialog" id="annotation-dialog">
                    <div class="dialog-header">
                        <h3>${this.getTitle()}</h3>
                        <button class="btn-close">&times;</button>
                    </div>
                    <div class="dialog-body">
                        <div class="form-group">
                            <label>时间范围</label>
                            <div class="time-range">
                                <input type="number" id="start-time" value="${this.currentTime}" step="0.1">
                                <span>至</span>
                                <input type="number" id="end-time" value="${this.currentTime + 10}" step="0.1">
                                <span>秒</span>
                            </div>
                        </div>
                        <div class="form-group">
                            <label>内容</label>
                            <textarea id="annotation-content" rows="4"></textarea>
                        </div>
                        ${this.renderExtraFields()}
                    </div>
                    <div class="dialog-footer">
                        <button class="btn-cancel">取消</button>
                        <button class="btn-confirm">确定</button>
                    </div>
                </div>
            `;

            document.body.insertAdjacentHTML('beforeend', dialogHtml);
            this.dialog = document.getElementById('annotation-dialog');

            // 绑定事件
            this.dialog.querySelector('.btn-close').addEventListener('click', () => {
                this.close();
                resolve({confirmed: false});
            });

            this.dialog.querySelector('.btn-cancel').addEventListener('click', () => {
                this.close();
                resolve({confirmed: false});
            });

            this.dialog.querySelector('.btn-confirm').addEventListener('click', () => {
                const result = this.getFormData();
                this.close();
                resolve({confirmed: true, ...result});
            });
        });
    }

    getTitle() {
        const titles = {
            'correction': '文字校对',
            'segment_label': '段落标注',
            'highlight': '重点标注',
            'knowledge_link': '知识关联',
            'teaching_point': '教学要点',
            'timestamp_note': '时间戳笔记'
        };
        return titles[this.type] || '添加标注';
    }

    renderExtraFields() {
        if (this.type === 'highlight') {
            return `
                <div class="form-group">
                    <label>重点类型</label>
                    <select id="highlight-type">
                        <option value="important">重要</option>
                        <option value="warning">注意</option>
                        <option value="tip">提示</option>
                        <option value="example">案例</option>
                    </select>
                </div>
            `;
        } else if (this.type === 'knowledge_link') {
            return `
                <div class="form-group">
                    <label>关联类型</label>
                    <select id="link-type">
                        <option value="theory">理论知识</option>
                        <option value="practice">实践方法</option>
                        <option value="case">案例</option>
                    </select>
                </div>
                <div class="form-group">
                    <label>搜索关键词</label>
                    <input type="text" id="link-search" placeholder="搜索相关内容...">
                </div>
            `;
        }
        return '';
    }

    getFormData() {
        return {
            start_time: parseFloat(document.getElementById('start-time').value),
            end_time: parseFloat(document.getElementById('end-time').value),
            content: document.getElementById('annotation-content').value,
            metadata: this.getMetadata()
        };
    }

    getMetadata() {
        const metadata = {};

        if (this.type === 'highlight') {
            metadata.highlight_type = document.getElementById('highlight-type').value;
        } else if (this.type === 'knowledge_link') {
            metadata.link_type = document.getElementById('link-type').value;
            metadata.search_query = document.getElementById('link-search').value;
        }

        return metadata;
    }

    close() {
        if (this.dialog) {
            this.dialog.remove();
        }
    }
}
```

---

## 📋 标注工作流程

### 典型标注流程

```
1. 上传音频 → 自动转写
2. 播放音频，查看转写文本
3. 发现错误或重点 → 创建标注
4. 保存标注 → 自动同步
5. 导出标注 → 用于检索/教学
```

### 标注质量保证

```python
# backend/services/annotation_validator.py
class AnnotationValidator:
    """标注验证器"""

    def validate(self, annotation: dict) -> dict:
        """验证标注数据"""
        errors = []

        # 1. 验证必填字段
        required_fields = ['audio_file_id', 'annotation_type']
        for field in required_fields:
            if field not in annotation:
                errors.append(f"缺少必填字段: {field}")

        # 2. 验证时间范围
        if 'start_time' in annotation and 'end_time' in annotation:
            if annotation['start_time'] >= annotation['end_time']:
                errors.append("start_time必须小于end_time")

        # 3. 验证标注类型
        valid_types = [
            'correction', 'segment_label', 'highlight',
            'knowledge_link', 'teaching_point', 'timestamp_note'
        ]
        if annotation.get('annotation_type') not in valid_types:
            errors.append(f"无效的标注类型: {annotation.get('annotation_type')}")

        # 4. 根据类型验证特定字段
        self._validate_by_type(annotation, errors)

        return {
            "valid": len(errors) == 0,
            "errors": errors
        }

    def _validate_by_type(self, annotation: dict, errors: list):
        """根据类型验证特定字段"""
        ann_type = annotation.get('annotation_type')

        if ann_type == 'correction':
            # 校对标注必须有original和corrected
            metadata = annotation.get('metadata', {})
            if 'original' not in metadata or 'corrected' not in metadata:
                errors.append("校对标注必须包含original和corrected字段")

        elif ann_type == 'highlight':
            # 重点标注必须有highlight_type
            metadata = annotation.get('metadata', {})
            if 'highlight_type' not in metadata:
                errors.append("重点标注必须包含highlight_type字段")
```

---

## 🔄 与转写系统集成

### 自动标注建议

```python
# backend/services/auto_annotation_suggester.py
class AutoAnnotationSuggester:
    """自动标注建议器"""

    async def suggest_corrections(self, transcript: str) -> List[dict]:
        """建议可能的转写错误

        基于词典匹配和语言模型
        """
        suggestions = []

        # 1. 功法术语词典
        terms = await self.load_glossary_terms()

        # 2. 检测可能的错误
        for term in terms:
            # 模糊匹配
            if self.fuzzy_match(transcript, term['incorrect']):
                suggestions.append({
                    "type": "correction",
                    "original": term['incorrect'],
                    "corrected": term['correct'],
                    "confidence": 0.8,
                    "reason": f"应该是'{term['correct']}'（功法术语）"
                })

        return suggestions

    async def suggest_highlights(self, segments: List[dict]) -> List[dict]:
        """建议重点内容

        基于关键词和情感分析
        """
        highlights = []

        # 关键词
        key_phrases = [
            "重要", "关键", "注意", "必须", "一定要",
            "核心", "要点", "记住", "特别"
        ]

        for segment in segments:
            text = segment['text']

            # 检测关键词
            for phrase in key_phrases:
                if phrase in text:
                    highlights.append({
                        "type": "highlight",
                        "segment_id": segment['id'],
                        "start_time": segment['start_time'],
                        "end_time": segment['end_time'],
                        "highlight_type": "important",
                        "confidence": 0.7,
                        "reason": f"包含关键词'{phrase}'"
                    })

        return highlights
```

---

## 📊 成功标准

| 指标 | 目标 | 验收方式 |
|------|------|----------|
| 标注创建速度 | < 3秒/个 | 性能测试 |
| 标注加载速度 | < 1秒 | 50个标注 |
| 标注准确性 | > 95% | 人工审核 |
| 用户满意度 | > 4.0/5.0 | 用户调查 |
| 标注类型支持 | 6种 | 功能测试 |

---

## ✅ 实施计划（更新双工程流）

### 团队B任务调整

| 任务ID | 任务 | 时间 | 说明 |
|--------|------|------|------|
| **B-1** | faster-whisper集成 | 2天 | 转写引擎 |
| **B-2** | 音频上传和预处理 | 2天 | 上传API |
| **B-3** | 异步转写Worker | 3天 | 核心服务 |
| **B-4** | 长音频分段处理 | 2天 | 分段逻辑 |
| **B-5** | 转写结果查询 | 2天 | 查询API |
| **B-6** | **标注系统开发** | **5天** | **新增** |
| **B-7** | 标注UI（波形+编辑器） | 3天 | **新增** |
| **B-8** | 导出(TXT/SRT/标注) | 2天 | 扩展 |
| **B-9** | 向量化集成 | 2天 | 集成 |
| **B-10** | 测试和文档 | 3天 | 完整文档 |
| **缓冲** | 意外问题 | 2天 | - |
| **总计** | **10项任务** | **28天** | - |

---

**文档状态**: ✅ **设计完成**

**版本**: v1.0.0

**下一步**: 开发标注系统

**众智混元，万法灵通** ⚡🚀
