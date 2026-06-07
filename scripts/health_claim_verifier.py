#!/usr/bin/env python3
"""
20集播客健康声明提取与分类验证脚本（v2 — 含中风险细分）

产出：
  data/health_claims/health_claim_verification_report.json  — 完整报告
  data/health_claims/health_claim_summary.md                — 可读摘要

三档分类（灵知提案 × 灵通问道补充）：
  📊 事实声明 — "气功可以降低血压"
  📜 传统说法 — "黄帝内经记载..."
  👤 个人证言 — "某人练习后康复了"

风险评级：
  ✅ 安全 — 无健康声明 或 传统说法有典籍支撑
  ⚠️ 中风险 — 事实声明无现代权威支撑
  ❌ 高风险 — 个人证言涉及重大疾病（癌症/白血病/肿瘤等）

中风险细分（v2新增）：
  chronic_factual — 事实声明涉及慢性病
  testimonial_chronic — 个人证言涉及慢性病
  traditional_disease — 传统理论涉及疾病
  alternative_medication — 替代药物暗示
  general_wellness — 温和声明（低假阳性）
"""

import re
import json
import os
from pathlib import Path
from datetime import datetime, timezone

EPISODES_DIR = Path("/home/ai/lingtongask/episodes")
OUTPUT_DIR = Path("/home/ai/lingzhi/data/health_claims")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# EP052-071
EPISODE_RANGE = range(52, 72)

# === 声明提取关键词 ===
# 健康效果声明动词
HEALTH_VERBS = [
    "改善", "治疗", "治愈", "康复", "缓解", "减轻", "消除", "调理",
    "降压", "降糖", "降脂", "止痛", "消炎", "安神", "助眠",
    "增强免疫", "提高免疫", "促进循环", "活血", "化瘀",
    "预防", "防止", "抗癌", "抗肿瘤", "抑制",
    "自愈", "修复", "恢复", "调节", "平衡",
]

# 重大疾病关键词（自动❌高风险）
CRITICAL_DISEASES = [
    "癌症", "癌", "肿瘤", "白血病", "尿毒症", "肾衰竭",
    "心梗", "脑梗", "中风", "肝硬化", "糖尿病并发症",
]

# 慢性病关键词（⚠️中风险）
CHRONIC_CONDITIONS = [
    "高血压", "低血压", "血压", "血糖", "糖尿病",
    "失眠", "抑郁", "焦虑", "关节炎", "颈椎病",
    "腰椎", "胃炎", "肠炎", "便秘", "腹泻",
    "哮喘", "气管炎", "皮肤病", "湿疹", "过敏",
    "头痛", "头晕", "耳鸣", "心悸", "胸闷",
]

# 来源引用关键词（有→可追溯）
SOURCE_MARKERS = [
    "研究表明", "研究显示", "根据研究", "数据表明", "数据显示",
    "黄帝内经", "伤寒论", "本草纲目", "难经", "金匮",
    "来源", "引自", "参考", "据记载", "书中",
    "实验", "临床试验", "统计", "文献",
]

# 替代医疗声明（"不需要药物"/"替代降压药"等）
ALTERNATIVE_TREATMENT = [
    "替代.*药", "不用.*药", "停.*药", "减.*药",
    "不需要.*药物", "摆脱.*药物", "代替.*药",
    "不用吃药", "不用服药", "无需.*药",
]


def extract_claims(text: str, ep_id: str) -> list[dict]:
    """从脚本文本中提取健康声明"""
    claims = []
    lines = text.split("\n")

    for i, line in enumerate(lines, 1):
        line = line.strip()
        if not line or len(line) < 10:
            continue

        # 检查是否包含健康声明
        has_health_verb = any(v in line for v in HEALTH_VERBS)
        has_disease = any(d in line for d in CRITICAL_DISEASES + CHRONIC_CONDITIONS)
        has_alternative = any(re.search(p, line) for p in ALTERNATIVE_TREATMENT)

        if not (has_health_verb or has_disease or has_alternative):
            continue

        # 分类声明类型
        claim_type = classify_claim_type(line)

        # 风险评级
        risk_level, risk_reason = assess_risk(line, claim_type)

        # 来源可追溯性
        has_source = any(s in line for s in SOURCE_MARKERS)

        # 中风险细分
        has_critical = any(d in line for d in CRITICAL_DISEASES)
        medium_subcategory = None
        if risk_level == "medium":
            mild_verbs = ["放松", "舒适", "平静", "安宁", "调理", "调节", "养护", "保养"]
            is_mild = any(v in line for v in mild_verbs) and not has_critical and not has_alternative
            if is_mild and claim_type == "traditional":
                medium_subcategory = "general_wellness"
            elif "传统理论" in risk_reason:
                medium_subcategory = "traditional_disease"
            elif "个人证言" in risk_reason and "慢性病" in risk_reason:
                medium_subcategory = "testimonial_chronic"
            elif "替代" in risk_reason:
                medium_subcategory = "alternative_medication"
            elif "慢性病" in risk_reason:
                medium_subcategory = "chronic_factual"
            else:
                medium_subcategory = "general_wellness"

        claims.append({
            "episode": ep_id,
            "line_number": i,
            "text": line[:300],
            "claim_type": claim_type,
            "risk_level": risk_level,
            "risk_reason": risk_reason,
            "medium_subcategory": medium_subcategory,
            "has_source": has_source,
            "keywords_found": {
                "critical_disease": [d for d in CRITICAL_DISEASES if d in line],
                "chronic_condition": [d for d in CHRONIC_CONDITIONS if d in line],
                "health_verbs": [v for v in HEALTH_VERBS if v in line],
                "alternative_treatment": has_alternative,
            }
        })

    return claims


def classify_claim_type(text: str) -> str:
    """分类声明类型：📊事实 / 📜传统 / 👤证言"""
    # 个人证言标志
    testimonial_markers = [
        "有人", "一位", "某位", "我朋友", "我亲戚", "我见过",
        "我认识", "她说", "他说", "他们", "客人", "患者",
        "八仙", "小组", "互助", "一位大姐", "一位先生",
        "当人", "身边",
    ]
    if any(m in text for m in testimonial_markers):
        return "testimonial"

    # 传统说法标志
    tradition_markers = [
        "黄帝内经", "伤寒论", "本草", "中医认为", "传统",
        "古", "经典", "道家", "佛家", "儒家",
        "理论", "理念", "哲学", "整体观",
    ]
    if any(m in text for m in tradition_markers):
        return "traditional"

    # 默认：事实声明
    return "factual"


def assess_risk(text: str, claim_type: str) -> tuple[str, str]:
    """评估风险等级"""
    has_critical = any(d in text for d in CRITICAL_DISEASES)
    has_alternative = any(re.search(p, text) for p in ALTERNATIVE_TREATMENT)

    # ❌ 高风险：个人证言涉及重大疾病
    if claim_type == "testimonial" and has_critical:
        return "high", "个人证言涉及重大疾病（癌症/白血病/肿瘤等）"

    # ❌ 高风险：替代药物声明
    if has_alternative and has_critical:
        return "high", "声称可替代药物治疗重大疾病"

    # ❌ 高风险：治愈/康复重大疾病
    if has_critical and any(v in text for v in ["治愈", "康复", "根治", "消除"]):
        return "high", f"声称治愈/康复重大疾病（含{[d for d in CRITICAL_DISEASES if d in text]}）"

    # ⚠️ 中风险：事实声明涉及慢性病但无来源
    has_chronic = any(d in text for d in CHRONIC_CONDITIONS)
    has_source = any(s in text for s in SOURCE_MARKERS)

    if claim_type == "factual" and has_chronic and not has_source:
        return "medium", "事实声明涉及慢性病，无来源引用"

    # ⚠️ 中风险：替代药物声明（非重大疾病）
    if has_alternative:
        return "medium", "暗示可替代药物治疗"

    # ⚠️ 中风险：个人证言涉及慢性病
    if claim_type == "testimonial" and has_chronic:
        return "medium", "个人证言涉及慢性病"

    # ⚠️ 中风险：传统说法涉及疾病治疗
    if claim_type == "traditional" and (has_chronic or has_critical):
        return "medium", "传统理论涉及疾病，需标注为传统理论"

    # ✅ 安全
    if claim_type == "traditional":
        return "low", "传统理论，未涉及具体疾病声明"

    if claim_type == "factual" and has_source:
        return "low", "事实声明有来源引用"

    return "low", "一般健康描述"


def verify_episode(ep_num: int) -> dict:
    """验证单集"""
    ep_id = f"EP{ep_num:03d}"
    ep_dir = EPISODES_DIR / f"ep{ep_num:03d}"
    script_path = ep_dir / "script.md"

    if not script_path.exists():
        return {"episode": ep_id, "error": "script.md not found"}

    text = script_path.read_text(encoding="utf-8")
    claims = extract_claims(text, ep_id)

    # 统计
    risk_counts = {"high": 0, "medium": 0, "low": 0}
    type_counts = {"factual": 0, "traditional": 0, "testimonial": 0}
    source_count = 0

    for c in claims:
        risk_counts[c["risk_level"]] += 1
        type_counts[c["claim_type"]] += 1
        if c["has_source"]:
            source_count += 1

    # 集级风险评级
    if risk_counts["high"] > 0:
        ep_risk = "high"
    elif risk_counts["medium"] > 0:
        ep_risk = "medium"
    else:
        ep_risk = "low"

    return {
        "episode": ep_id,
        "total_claims": len(claims),
        "risk_distribution": risk_counts,
        "type_distribution": type_counts,
        "traceable_claims": source_count,
        "traceability_rate": round(source_count / len(claims), 3) if claims else None,
        "episode_risk": ep_risk,
        "claims": claims,
    }


def main():
    print("=" * 60)
    print("20集播客健康声明验证 (EP052-071)")
    print("=" * 60)

    results = {}
    for ep in EPISODE_RANGE:
        print(f"\r  验证 EP{ep:03d}...", end="", flush=True)
        results[f"EP{ep:03d}"] = verify_episode(ep)

    print("\r  完成！                    ")

    # 汇总
    total_claims = sum(r.get("total_claims", 0) for r in results.values())
    total_high = sum(r.get("risk_distribution", {}).get("high", 0) for r in results.values())
    total_medium = sum(r.get("risk_distribution", {}).get("medium", 0) for r in results.values())
    total_low = sum(r.get("risk_distribution", {}).get("low", 0) for r in results.values())

    ep_risks = {ep: r["episode_risk"] for ep, r in results.items()}
    eps_high = [ep for ep, r in ep_risks.items() if r == "high"]
    eps_medium = [ep for ep, r in ep_risks.items() if r == "medium"]
    eps_low = [ep for ep, r in ep_risks.items() if r == "low"]

    summary = {
        "verified_at": datetime.now(timezone.utc).isoformat(),
        "verifier": "lingzhi",
        "method": "keyword_extraction + rule_based_classification",
        "classification": {
            "claim_types": ["factual(事实)", "traditional(传统)", "testimonial(证言)"],
            "risk_levels": ["high(高)", "medium(中)", "low(低)"],
        },
        "totals": {
            "episodes": len(results),
            "total_claims": total_claims,
            "high_risk_claims": total_high,
            "medium_risk_claims": total_medium,
            "low_risk_claims": total_low,
        },
        "episode_risk_distribution": {
            "high": eps_high,
            "medium": eps_medium,
            "low": eps_low,
        },
    }

    report = {
        "summary": summary,
        "episodes": results,
    }

    # 写入文件
    output_path = OUTPUT_DIR / "health_claim_verification_report.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(f"\n{'='*60}")
    print(f"验证完成")
    print(f"{'='*60}")
    print(f"  总集数: {len(results)}")
    print(f"  总声明数: {total_claims}")
    print(f"  ❌ 高风险声明: {total_high}")
    print(f"  ⚠️ 中风险声明: {total_medium}")
    print(f"  ✅ 低风险声明: {total_low}")
    print(f"\n  集级分级:")
    print(f"  ❌ 高风险集({len(eps_high)}): {', '.join(eps_high) if eps_high else '无'}")
    print(f"  ⚠️ 中风险集({len(eps_medium)}): {', '.join(eps_medium) if eps_medium else '无'}")
    print(f"  ✅ 低风险集({len(eps_low)}): {', '.join(eps_low) if eps_low else '无'}")
    print(f"\n  报告: {output_path}")

    return report


if __name__ == "__main__":
    main()
