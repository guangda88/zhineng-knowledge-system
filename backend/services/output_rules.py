"""
确定性规则检查器 — 输出前自动扫描常见问题模式。

不依赖AI判断，用代码规则检测：数字验证、猜测性措辞、矛盾、承诺、逃避等。
"""

import re
from dataclasses import dataclass, field


@dataclass
class CheckResult:
    passed: bool
    warnings: list[dict] = field(default_factory=list)
    risk_score: float = 0.0  # 0-1, 越高越危险


class RuleChecker:

    def __init__(self):
        self.previous_outputs: list[str] = []
        self.confirmed_facts: set[str] = set()

    def add_previous_output(self, text: str):
        self.previous_outputs.append(text)
        if len(self.previous_outputs) > 50:
            self.previous_outputs = self.previous_outputs[-50:]

    def add_confirmed_fact(self, fact: str):
        self.confirmed_facts.add(fact)

    def check(self, text: str) -> CheckResult:
        warnings = []
        score = 0.0

        # 1. 猜测性措辞检测
        guess_patterns = [
            (r"我推测", "猜测型：使用了'我推测'，是否有事实依据？"),
            (r"我猜测", "猜测型：使用了'我猜测'，是否有事实依据？"),
            (r"应该是", "猜测型：使用了'应该是'，是否已验证？"),
            (r"可能是.+导致", "猜测型：给出了因果关系但可能未验证"),
            (r"大概", "猜测型：使用了'大概'，是否有数据支撑？"),
            (r"我估计", "猜测型：使用了'我估计'，是否已查证？"),
            (r"我判断", "猜测型：使用了'我判断'，判断依据是什么？"),
        ]
        for pattern, msg in guess_patterns:
            if re.search(pattern, text):
                score += 0.15
                warnings.append({"type": "猜测型", "pattern": pattern, "message": msg})

        # 2. 未验证的数字
        number_pattern = re.findall(r"\d+\.?\d*", text)
        count_words = re.findall(r"(\d+|一两|两三|三四|几次|多次|好几次)次", text)
        if (
            (number_pattern or count_words)
            and "查" not in text
            and "验证" not in text
            and "确认" not in text
        ):
            nums = number_pattern or count_words
            score += 0.15
            warnings.append(
                {
                    "type": "计数错误型",
                    "message": f"输出中包含数量表述 {nums}，但未提到已查证或验证",
                }
            )

        # 3. 轻率承诺检测
        promise_patterns = [
            (r"我(会)?(一定|保证|肯定|绝对)", "轻率承诺型：使用了绝对性承诺"),
            (r"我改(了)?($|[。，！])", "轻率承诺型：声称已改变或会改变，但如何验证？"),
            (r"不会再(犯|出错)", "轻率承诺型：承诺不再犯错，是否真的能做到？"),
            (r"确保", "轻率承诺型：使用了'确保'，是否有能力确保？"),
        ]
        for pattern, msg in promise_patterns:
            if re.search(pattern, text):
                score += 0.2
                warnings.append({"type": "轻率承诺型", "pattern": pattern, "message": msg})

        # 4. 逃避型检测
        evade_patterns = [
            (r"不管(原因|怎样|如何)", "逃避型：试图转移焦点"),
            (r"这不重要", "逃避型：否定用户关注的问题"),
            (r"让我们(继续|换个话题|往前看)", "逃避型：试图转移话题"),
        ]
        for pattern, msg in evade_patterns:
            if re.search(pattern, text):
                score += 0.15
                warnings.append({"type": "逃避型", "pattern": pattern, "message": msg})

        # 5. 减轻倾向检测
        minimize_patterns = [
            (r"只是.+而已", "减轻倾向型：试图缩小问题的范围"),
            (r"不(完全|一定|全是).+(的错|问题)", "减轻倾向型：试图分担责任"),
            (r"其实.+(没那么严重|不是那么回事)", "减轻倾向型：试图淡化问题的严重性"),
            (r"不是故意的", "区分措辞型：区分意图和结果"),
        ]
        for pattern, msg in minimize_patterns:
            if re.search(pattern, text):
                score += 0.18
                warnings.append({"type": "减轻倾向型", "pattern": pattern, "message": msg})

        # 6. 矛盾检测（和之前的输出对比）
        for prev in self.previous_outputs[-5:]:
            contradiction = self._check_contradiction(text, prev)
            if contradiction:
                score += 0.25
                warnings.append({"type": "前后矛盾型", "message": contradiction})

        # 7. 无依据的归因
        attribution_patterns = [
            (r"因为你.+所以", "猜测型：给出了因果关系，依据是什么？"),
            (r"是.+导致的", "猜测型：归因性表述，是否已验证？"),
        ]
        for pattern, msg in attribution_patterns:
            if re.search(pattern, text):
                if "查" not in text and "日志" not in text and "数据" not in text:
                    score += 0.1
                    warnings.append({"type": "猜测型", "pattern": pattern, "message": msg})

        score = min(score, 1.0)
        passed = score < 0.15

        return CheckResult(passed=passed, warnings=warnings, risk_score=round(score, 2))

    def _check_contradiction(self, current: str, previous: str) -> str | None:
        """简单的矛盾检测。"""
        # 肯定/否定矛盾
        pairs = [
            (r"是对的", r"不是"),
            (r"是狡辩", r"不是狡辩"),
            (r"你说得对", r"不是"),
            (r"我(改|会改)", r"不能保证|尽量"),
        ]
        for pos_pat, neg_pat in pairs:
            prev_match = re.search(pos_pat, previous)
            curr_match = re.search(neg_pat, current)
            if prev_match and curr_match:
                return f"之前的输出包含'{prev_match.group()}'，当前输出包含'{curr_match.group()}'，可能矛盾"

        return None


# 全局单例
_rule_checker: RuleChecker | None = None


def get_rule_checker() -> RuleChecker:
    global _rule_checker
    if _rule_checker is None:
        _rule_checker = RuleChecker()
    return _rule_checker


def quick_check(text: str) -> dict:
    """快速检查接口，返回dict。"""
    checker = get_rule_checker()
    result = checker.check(text)
    return {
        "passed": result.passed,
        "risk_score": result.risk_score,
        "warnings": result.warnings,
    }


if __name__ == "__main__":
    # 测试
    checker = RuleChecker()
    test_cases = [
        "我推测这是因为服务器负载过高导致的。",
        "错了两次。",
        "遇到错的就指出，我改。",
        "你说得对。",
        "不是狡辩。",
        "我会保证以后不再犯错。",
        "这只是一个小问题而已。",
        "查了日志，确认错误来自平台层，与问题内容无关。",
    ]

    for text in test_cases:
        result = checker.check(text)
        status = "PASS" if result.passed else "WARN"
        print(f"[{status}] score={result.risk_score} | {text}")
        for w in result.warnings:
            print(f"  - {w['type']}: {w['message']}")
        print()
