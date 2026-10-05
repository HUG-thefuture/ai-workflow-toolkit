# 求职材料处理 AI 工作流

![CI](https://github.com/HUG-thefuture/ai-workflow-toolkit/actions/workflows/ci.yml/badge.svg)

两个纯 Python、零第三方依赖、确定性可复现的工作流项目 + 一份 Dify 工作流编排定义：

```
project/
├── email_classifier/     邮件分类与任务创建流程（简历项目二口径）
│   ├── classify.py       分类→抽取→校验(失败重试)→意图判重 全链路
│   ├── test_classify.py  pytest 单测（7 例）
│   └── classify_result.json
├── job_workflow/         岗位描述抽取工作流（简历项目一口径）
│   ├── workflow.py       input_clean→llm_extract→rule_validate(重试/转人工)→汇总
│   ├── regress.py        20 份模拟 JD 回归（pytest）
│   ├── dify/job_workflow_dsl.yml   等价 Dify 工作流 DSL
│   └── data/jobs/ (20 份) + reports/regression_summary.json
└── requirements.txt
```

## 快速开始（Python 3.11+，零依赖）

```bash
# 邮件分类全链路（含内置断言）→ classify_result.json
python email_classifier/classify.py
python -m pytest email_classifier/test_classify.py -v     # 单测 7 例

# 岗位抽取工作流（带重试/转人工路径与节点耗时留存）
python job_workflow/workflow.py "岗位：Python后端。地点：成都。3 年经验，本科。熟悉 Python/MySQL。"
python -m pytest job_workflow/regress.py -v               # 20 份 JD 回归 + 空输入转人工
```

## 设计要点（面试口径）

- **显式编排而非隐式 Agent**：步骤固定、每步输入输出/耗时/错误落 JSON，失败可重试可转人工——工作流的价值在可观测与可控，Agent 的价值在开放路径，两者选型理由要能讲清。
- **LLM 可插拔**：`LLM_PROVIDER=mock`（规则式、离线确定性）↔ `openai_compatible`（环境变量注入 KEY/BASE_URL，见各脚本内 Provider 类）；mock 保证回归可复现，真实 API 只换实现不换接口。
- **意图签名判重**：类别+截止时间相同即视为重复，文本改写不影响识别。

## 验证记录（2026-09-14 复验）

- `python email_classifier/classify.py` → 5 封分类、创建 2 任务、判重拦截 1，内置断言全过。
- `python job_workflow/regress.py` → **2 passed**（20 份 JD 全 done、jd_05/15 空缺转人工、空输入重试 2 次后转人工）。
- `python -m pytest email_classifier/test_classify.py job_workflow/test_retry_paths.py job_workflow/regress.py` → **13 passed**（classify 7 + 重试路径 4 + 回归 2）。

---

## 产品视角（面试可讲）

- **目标用户**：求职期管理多渠道招聘信息的个人；可平移到任何"信息分类+去重+待办"流程。
- **解决的问题**：招聘信息易漏、易重复处理；分类后还要防同一事件重复建任务。
- **核心场景**：信息→意图分类→（类别+截止）签名判重→可重试错误自动重试→不可恢复转人工。
- **成功指标（实测）**：13 例回归全绿；判重拦截"同日面试邮件"有回归锚定；due=None 误杀 bug 修复留痕。
- **未来计划**：IMAP 接入真实邮箱；重复任务看板；Dify DSL 导入验收（当前为显式 Python 编排口径）。
