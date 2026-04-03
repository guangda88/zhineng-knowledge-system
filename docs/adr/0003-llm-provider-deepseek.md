# ADR-0003: LLM 提供商选型 — DeepSeek API

**状态**: 已接受
**日期**: 2026-04-03
**替代**: LINGZHI_SYSTEM_PRINCIPLES 中 OpenAI API 的引用

## 背景

LINGZHI_SYSTEM_PRINCIPLES 文档将 OpenAI API 列为 LLM 提供商，但实际系统使用 DeepSeek API。此变更未在 ADR 中记录，导致文档与实现不一致。

## 决策

采用 DeepSeek API 作为主要 LLM 提供商。

## 理由

1. **成本效益**：DeepSeek API 价格远低于 OpenAI，适合中文领域应用
2. **中文能力**：DeepSeek 在中文理解和生成方面表现优异
3. **国产合规**：数据不出境，满足国内部署需求
4. **API 兼容**：DeepSeek API 与 OpenAI 格式兼容，迁移成本低

## 后果

- 环境变量 `DEEPSEEK_API_KEY` 为必需配置
- 所有文档中 OpenAI API 引用需更新为 DeepSeek
- 如未来需要切换提供商，需创建新 ADR 记录
