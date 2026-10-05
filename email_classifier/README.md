# email_classifier：招聘邮件意图分类与判重

对招聘相关邮件做意图分类（面试/笔试/offer/拒信/通知等），并以「类别 + 截止时间」意图签名判重，避免同一事件重复创建任务或被误判重复而静默丢失。

## 快速开始

```bash
python email_classifier/classify.py       # 分类 + 判重 → classify_result.json（mock，零依赖离线可跑）
pip install pytest                        # 仅测试需要
python -m pytest email_classifier -q      # 单测：含"同日面试邮件被拦截"的判重回归
```

## 关键机制（面试点）

- **意图签名判重**：`dedup_check` 以（类别, 截止时间）为签名。2026-09 修复过 `due=None` 时被误判为重复、导致任务静默丢失的 bug，回归里保留"同日面试邮件拦截 1 条"的断言；
- **LLM 可插拔**：Provider 抽象 mock ↔ openai_compatible（环境变量注入 KEY，占位符快速失败）。mock 全离线可跑；真实 LLM 路径已实现但未纳入回归，如实标注。
