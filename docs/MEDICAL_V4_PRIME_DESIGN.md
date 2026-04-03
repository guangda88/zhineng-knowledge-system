# 医学 V4' 维度体系设计文档

**版本**: V4'-Medical
**设计日期**: 2026-04-02
**基于**: 智能气功 V4.0 框架

---

## 一、设计原则

### 1.1 与气功 V4 的对应关系

| 气功 V4 | 医学 V4' | 变化说明 |
|---------|-----------|----------|
| theory_system | medical_system | 理论体系 → 医学体系 |
| content_topic | medical_topic | 内容主题 → 医学主题 |
| gongfa_method | treatment_method | 功法 → 治疗方法 |
| teaching_level | difficulty_level | 教学层次 → 难度等级 |
| discipline | medical_discipline | 教材归属 → 医学学科 |
| timeline | dynasty_period | 时间线 → 朝代时期 |
| speaker | author | 主讲人 → 作者/医家 |
| media_format | document_type | 媒体格式 → 文档类型 |
| security_level | access_level | 安全级别 → 访问级别 |

---

## 二、维度体系定义

### 2.1 M类：医学体系 (Medical System) - 替代 S/A 类

| 维度代码 | 维度名称 | 选项 | 说明 |
|---------|---------|------|------|
| **medical_system** | 医学体系 | 中医 | 传统中医理论体系 |
| | | 西医 | 现代医学体系 |
| | | 中西医结合 | 中西医结合医学 |
| | | 民族医学 | 少数民族医学 |
| | | 其他医学 | 其他医学体系 |

### 2.2 C类：医学主题 (Medical Topic) - 替代 B类内容

| 一级分类 | 二级选项 | 说明 |
|---------|---------|------|
| **基础理论** | 中医基础 | 阴阳五行、脏腑经络、气血津液 |
| | | 西医基础 | 解剖、生理、病理、药理 |
| | | 诊断学 | 望闻问切、体格检查 |
| **临床各科** | 内科 | 内科疾病 |
| | | 外科 | 外科疾病 |
| | | 妇科 | 妇科疾病 |
| | | 儿科 | 儿科疾病 |
| | | 骨伤科 | 骨折、脱臼、伤筋 |
| | | 针灸科 | 针灸、艾灸、拔罐 |
| | | 推拿科 | 推拿按摩 |
| **治疗方法** | 方药 | 中药方剂 |
| | | 针灸 | 针灸疗法 |
| | | 推拿 | 推拿按摩 |
| | | 气功 | 气功疗法 |
| | | 食疗 | 食疗调理 |
| **预防保健** | 养生 | 养生保健 |
| | | 康复 | 康复医学 |

### 2.3 T类：治疗技术 (Treatment) - 替代 C 类功法

| 技术分类 | 说明 |
|---------|------|
| **方剂技术** | 汤头、散剂、丸剂、膏剂、丹剂、酒剂 |
| **针灸技术** | 毫针、艾灸、拔罐、刮痧、穴位注射 |
| **推拿技术** | 推拿、按摩、正骨、点穴 |
| **气功技术** | 内养功、松静功、行功、保健功 |
| **外治法** | 熏法、洗法、敷贴、熏洗 |
| **食疗技术** | 药膳、食养、饮食调理 |

### 2.4 D类：难度等级 (Difficulty) - 替代 D 类教学层次

| 等级 | 说明 | 适用人群 |
|------|------|----------|
| **入门** | 基础概念、简单操作 | 一般大众 |
| **初级** | 基本理论、基础操作 | 初学者 |
| **中级** | 系统理论、熟练操作 | 从业人员 |
| **高级** | 深入理论、复杂操作 | 专业人员 |
| **专家** | 精深理论、创新应用 | 专家学者 |

### 2.5 K类：医学学科 (Medical Discipline) - 对应气功 discipline

| 学科分类 | 说明 | 对应古籍 |
|---------|------|----------|
| **基础理论** | 中医基础理论 | 《黄帝内经》《难经》 |
| **伤寒** | 伤寒杂病论 | 《伤寒论》《金匮要略》 |
| **金匮** | 金匮要略 | 《金匮要略》 |
| **温病** | 温病学 | 《温热经纬》《温病条辨》 |
| **内科** | 内科杂病 | 各家内科专著 |
| **外科** | 外科伤科 | 《外科正宗》 |
| **妇科** | 妇科产科 | 《傅青主女科》 |
| **儿科** | 儿科 | 《小儿药证直诀》 |
| **针灸** | 针灸推拿 | 《针灸甲乙经》 |
| **本草** | 中药学 | 《本草纲目》 |
| **方剂** | 方剂学 | 《太平惠民和剂局方》 |

### 2.6 传承维度 (Heritage) - 医学特色

| 维度 | 说明 | 选项 |
|------|------|------|
| **朝代** | 成书朝代 | 先秦、汉、唐、宋、金元、明、清、近现代 |
| **医家** | 作者或医家 | 扁鹊、华佗、张仲景、孙思邈、李时珍... |
| **流派** | 医学流派 | 伤寒派、温补派、滋阴派、火神派... |

---

## 三、数据模型

### 3.1 JSONB 结构示例

```json
{
  "medical_system": "中医",
  "medical_topic": ["基础理论", "中医基础"],
  "treatment_method": "方药",
  "difficulty_level": "中级",
  "medical_discipline": "内科",
  "dynasty": "清代",
  "author": "叶天士",
  "school": "温病派",
  "document_type": "古籍",
  "access_level": "public"
}
```

### 3.2 数据库表设计

```sql
-- 扩展 documents 表支持医学分类
ALTER TABLE documents ADD COLUMN IF NOT EXISTS
  category VARCHAR(50) NOT NULL
  CHECK (category IN ('气功', '中医', '西医', '国学', '其他'));

-- 医学维度字段
ALTER TABLE documents ADD COLUMN IF NOT EXISTS
  medical_dims JSONB DEFAULT '{}'::jsonb;

-- GIN 索引
CREATE INDEX IF NOT EXISTS idx_documents_medical_dims
  ON documents USING GIN (medical_dims)
  WHERE category IN ('中医', '西医');

-- 医学受控词表
CREATE TABLE IF NOT EXISTS medical_dimension_vocab (
    dimension_code VARCHAR(50) PRIMARY KEY,
    dimension_name VARCHAR(100),
    category VARCHAR(10),  -- M/C/T/D/K/H
    sub_items JSONB
);
```

---

## 四、受控词表初始化

### 4.1 医学体系

```sql
INSERT INTO medical_dimension_vocab (dimension_code, dimension_name, category, sub_items) VALUES
('medical_system', '医学体系', 'M', '[
  {"code": "tcm", "name": "中医", "selected": true},
  {"code": "wm", "name": "西医", "selected": false},
  {"code": "integrated", "name": "中西医", "selected": false},
  {"code": "ethnic", "name": "民族医学", "selected": false}
]');
```

### 4.2 医学主题

```sql
INSERT INTO medical_dimension_vocab (dimension_code, dimension_name, category, sub_items) VALUES
('medical_topic', '医学主题', 'C', '[
  {"code": "basic_theory", "name": "基础理论", "subs": ["中医基础", "西医基础", "诊断学"]},
  {"code": "clinical", "name": "临床各科", "subs": ["内科", "外科", "妇科", "儿科", "骨伤科", "针灸科", "推拿科"]},
  {"code": "treatment", "name": "治疗方法", "subs": ["方药", "针灸", "推拿", "气功", "食疗", "外治"]},
  {"code": "prevention", "name": "预防保健", "subs": ["养生", "康复"]}
]');
```

### 4.3 治疗技术

```sql
INSERT INTO medical_dimension_vocab (dimension_code, dimension_name, category, sub_items) VALUES
('treatment_method', '治疗技术', 'T', '[
  {"code": "formula", "name": "方剂技术", "subs": ["汤头", "散剂", "丸剂", "膏剂", "丹剂"]},
  {"code": "acupuncture", "name": "针灸技术", "subs": ["毫针", "艾灸", "拔罐", "刮痧"]},
  {"code": "tuina", "name": "推拿技术", "subs": ["推拿", "按摩", "正骨", "点穴"]},
  {"code": "qigong", "name": "气功技术", "subs": ["内养功", "松静功", "行功", "保健功"]}
]');
```

---

## 五、实施路线图

```
Phase 1: 数据准备 (1周)
├── 清理 guoxue.db 中医学相关数据
├── 提取中医古籍、方剂、针灸等内容
└── 建立医学测试数据集

Phase 2: 维度测试 (1周)
├── 实现 MedicalContentParser
├── 测试标注准确率
└── 优化提取规则

Phase 3: 批量标注 (2周)
├── 对医学文档进行 V4' 标注
├── 建立医学索引
└── 实现医学检索 API

Phase 4: 应用上线 (1周)
├── 医学检索界面
├── 跨领域检索 (气功+医学)
└── 统计分析报表
```

---

## 六、与气功 V4 的对比

| 特性 | 气功 V4 | 医学 V4' |
|------|---------|-----------|
| **核心领域** | 智能气功 | 中医医学 |
| **理论体系** | 混元整体理论 | 阴阳五行 |
| **方法体系** | 三阶段六步功法 | 方药针灸推拿 |
| **目标** | 练功强身 | 防病治病 |
| **资料类型** | 讲座录音/视频 | 古籍/医案/方剂 |

---

## 七、应用场景

### 7.1 跨领域检索

用户问题："如何用气功辅助治疗高血压"

```
检索逻辑:
1. 气功库 → 查找"高血压"相关功法
2. 医学库 → 查找"高血压"相关方剂
3. 关联分析 → 提供综合建议

结果: 形神庄 + 某中药方 + 生活调理建议
```

### 7.2 知识图谱构建

```
智能气功 ←→ 气功医疗 ←→ 中医基础
     ↓              ↓           ↓
   混元整体理论   针灸推拿    养生康复
```

---

## 八、成功指标

| 指标 | 目标值 |
|------|--------|
| 医学文档数 | 10,000+ |
| 标注覆盖率 | 80%+ |
| 检索响应时间 | <100ms |
| 跨领域检索 | 支持 |

---

**设计人**: Claude AI
**审核**: 待定
**状态**: 设计完成，待实施
