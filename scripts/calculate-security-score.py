#!/usr/bin/env python3
"""
Security Score Calculator

计算安全评分基于扫描结果。

评分标准:
- 后端: 60分
  - Bandit (40分): 0 HIGH = 40分, 1 HIGH = 30分, >1 HIGH = 0分
  - Safety (20分): 0 CRITICAL/HIGH = 20分, 1 MEDIUM = 15分, >1 MEDIUM = 5分
- 前端: 40分
  - NPM Audit (40分): 0 CRITICAL/HIGH = 40分, 1 MEDIUM = 20分, >1 MEDIUM = 0分

总分: 100分
等级: A (90-100), B (80-89), C (70-79), D (60-69), F (<60)
"""

import json
import sys
from pathlib import Path
from typing import Any, Dict


class SecurityScoreCalculator:
    """安全评分计算器"""

    def __init__(self):
        self.backend_bandit_issues = 0
        self.backend_bandit_high = 0
        self.backend_safety_vulns = 0
        self.backend_safety_high_severity = 0
        self.frontend_vulns = 0
        self.frontend_critical_high = 0

    def parse_bandit_report(self, report_path: str):
        """解析Bandit报告"""
        try:
            with open(report_path, "r") as f:
                report = json.load(f)

            results = report.get("results", [])

            self.backend_bandit_issues = len(results)
            self.backend_bandit_high = len(
                [r for r in results if r.get("issue_severity") == "HIGH"]
            )

        except Exception as e:
            print(f"Error parsing bandit report: {e}", file=sys.stderr)

    def parse_safety_report(self, report_path: str):
        """解析Safety报告"""
        try:
            with open(report_path, "r") as f:
                report = json.load(f)

            vulnerabilities = report.get("vulnerabilities", [])
            self.backend_safety_vulns = len(vulnerabilities)

            self.backend_safety_high_severity = len(
                [
                    v
                    for v in vulnerabilities
                    if v.get("advisory", {}).get("severity") in ["high", "critical"]
                ]
            )

        except Exception as e:
            print(f"Error parsing safety report: {e}", file=sys.stderr)

    def parse_npm_audit_report(self, report_path: str):
        """解析NPM审计报告"""
        try:
            with open(report_path, "r") as f:
                report = json.load(f)

            vulnerabilities = report.get("vulnerabilities", {})
            metadata = report.get("metadata", {})
            vuln_metadata = metadata.get("vulnerabilities", {})

            self.frontend_vulns = vuln_metadata.get("total", 0)
            self.frontend_critical_high = vuln_metadata.get("critical", 0) + vuln_metadata.get(
                "high", 0
            )

        except Exception as e:
            print(f"Error parsing npm audit report: {e}", file=sys.stderr)

    def calculate_backend_score(self) -> int:
        """计算后端评分"""
        # Bandit评分 (40分)
        if self.backend_bandit_high == 0:
            bandit_score = 40
        elif self.backend_bandit_high == 1:
            bandit_score = 30
        else:
            bandit_score = 0

        # Safety评分 (20分)
        if self.backend_safety_high_severity == 0:
            safety_score = 20
        elif self.backend_safety_high_severity == 1:
            safety_score = 15
        elif self.backend_safety_high_severity <= 2:
            safety_score = 10
        else:
            safety_score = 5

        # 总分
        backend_score = bandit_score + safety_score

        # 确保不超过60分
        return min(backend_score, 60)

    def calculate_frontend_score(self) -> int:
        """计算前端评分"""
        if self.frontend_critical_high == 0:
            return 40
        elif self.frontend_critical_high == 1:
            return 20
        elif self.frontend_critical_high <= 2:
            return 10
        else:
            return 0

    def calculate_grade(self, score: int) -> str:
        """确定等级"""
        if score >= 90:
            return "A"
        elif score >= 80:
            return "B"
        elif score >= 70:
            return "C"
        elif score >= 60:
            return "D"
        else:
            return "F"

    def generate_report(self) -> Dict[str, Any]:
        """生成评分报告"""
        backend_score = self.calculate_backend_score()
        frontend_score = self.calculate_frontend_score()
        total_score = backend_score + frontend_score
        grade = self.calculate_grade(total_score)

        return {
            "overall": {
                "score": total_score,
                "grade": grade,
                "max_score": 100,
            },
            "backend": {
                "score": backend_score,
                "max_score": 60,
                "bandit": {
                    "issues": self.backend_bandit_issues,
                    "high_severity": self.backend_bandit_high,
                    "score": (
                        40
                        if self.backend_bandit_high == 0
                        else (30 if self.backend_bandit_high == 1 else 0)
                    ),
                },
                "safety": {
                    "vulnerabilities": self.backend_safety_vulns,
                    "high_severity": self.backend_safety_high_severity,
                    "score": (
                        20
                        if self.backend_safety_high_severity == 0
                        else (15 if self.backend_safety_high_severity == 1 else 5)
                    ),
                },
            },
            "frontend": {
                "score": frontend_score,
                "max_score": 40,
                "npm_audit": {
                    "vulnerabilities": self.frontend_vulns,
                    "critical_high": self.frontend_critical_high,
                    "score": (
                        40
                        if self.frontend_critical_high == 0
                        else (20 if self.frontend_critical_high == 1 else 0)
                    ),
                },
            },
            "recommendations": self._get_recommendations(),
        }

    def _get_recommendations(self) -> list:
        """生成改进建议"""
        recommendations = []

        if self.backend_bandit_high > 0:
            recommendations.append(
                {
                    "priority": "HIGH",
                    "area": "Backend Security",
                    "message": f"Fix {self.backend_bandit_high} HIGH severity Bandit issues",
                    "action": "Review and fix security vulnerabilities in backend code",
                }
            )

        if self.backend_safety_high_severity > 0:
            recommendations.append(
                {
                    "priority": "HIGH",
                    "area": "Dependency Security",
                    "message": f"Update {self.backend_safety_high_severity} vulnerable Python packages",
                    "action": "Run `pip install --upgrade` for affected packages",
                }
            )

        if self.frontend_critical_high > 0:
            recommendations.append(
                {
                    "priority": "HIGH",
                    "area": "Frontend Security",
                    "message": f"Fix {self.frontend_critical_high} CRITICAL/HIGH NPM vulnerabilities",
                    "action": "Run `npm audit fix` to update vulnerable packages",
                }
            )

        if self.frontend_vulns > 0 and self.frontend_critical_high == 0:
            recommendations.append(
                {
                    "priority": "MEDIUM",
                    "area": "Frontend Security",
                    "message": f"Address {self.frontend_vulns} remaining NPM vulnerabilities",
                    "action": "Review and update affected dependencies",
                }
            )

        return recommendations


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description="Calculate security score")
    parser.add_argument(
        "--bandit-report",
        help="Path to bandit report JSON",
        default="services/web_app/backend/bandit-report.json",
    )
    parser.add_argument(
        "--safety-report",
        help="Path to safety report JSON",
        default="services/web_app/backend/safety-report.json",
    )
    parser.add_argument(
        "--npm-report",
        help="Path to NPM audit report JSON",
        default="services/web_app/frontend/npm-audit-report.json",
    )
    parser.add_argument("--output", help="Output JSON file", default="security-report.json")

    args = parser.parse_args()

    # 创建计算器
    calculator = SecurityScoreCalculator()

    # 解析报告
    if Path(args.bandit_report).exists():
        calculator.parse_bandit_report(args.bandit_report)

    if Path(args.safety_report).exists():
        calculator.parse_safety_report(args.safety_report)

    if Path(args.npm_report).exists():
        calculator.parse_npm_audit_report(args.npm_report)

    # 生成报告
    report = calculator.generate_report()

    # 输出报告
    with open(args.output, "w") as f:
        json.dump(report, f, indent=2)

    # 打印摘要
    print("\n" + "=" * 60)
    print("Security Score Report")
    print("=" * 60)
    print(f"\nOverall Score: {report['overall']['score']}/100")
    print(f"Grade: {report['overall']['grade']}")
    print(f"\nBackend: {report['backend']['score']}/60")
    print(f"  - Bandit: {report['backend']['bandit']['score']}/40")
    print(f"  - Safety: {report['backend']['safety']['score']}/20")
    print(f"\nFrontend: {report['frontend']['score']}/40")
    print(f"  - NPM Audit: {report['frontend']['npm_audit']['score']}/40")

    if report["recommendations"]:
        print("\nRecommendations:")
        for i, rec in enumerate(report["recommendations"], 1):
            print(f"\n{i}. [{rec['priority']}] {rec['area']}")
            print(f"   {rec['message']}")
            print(f"   Action: {rec['action']}")

    print("\n" + "=" * 60)


if __name__ == "__main__":
    main()
