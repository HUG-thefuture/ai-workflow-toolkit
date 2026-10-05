# -*- coding: utf-8 -*-
"""求职材料处理 AI 工作流（简历项目一）——纯 Python 等价实现。

编排结构（与 dify/job_workflow_dsl.yml 中的 Dify 工作流一一对应）：
  input_clean → llm_extract（LLM Provider 抽象，mock 离线/可切真实 API）
  → rule_validate（JSON 字段校验，失败重试 N 次 → 转人工确认）
  → condition_branch（完整/缺失字段分支）→ summarize（结果汇总 + 节点耗时/错误留存）

简历口径：要求模型输出固定 JSON，Python 节点校验字段并在失败时重试或转人工确认；
保存输入、输出、节点耗时与错误信息；20 份模拟岗位描述执行回归测试。
"""
import json
import os
import re
import time
from dataclasses import dataclass, field

# ---------------------------------------------------------------- LLM Provider 抽象
SKILL_BANK = ["Python", "Java", "MySQL", "FastAPI", "Spring Boot", "Vue", "Docker",
              "Git", "Linux", "SQL", "pandas", "pytest", "Selenium", "Redis", "LangGraph"]
DEGREE_RE = re.compile(r"(本科|硕士|研究生|大专及以上|统招)")
FIELD_HINTS = {"position": r"岗位[:：]\s*(\S+)", "location": r"(地点|城市)[:：]\s*(\S+)"}


class MockLLM:
    """离线 mock：基于规则的确定性抽取，保证回归可复现。"""

    def extract(self, jd_text: str) -> dict:
        skills = [s for s in SKILL_BANK if s.lower() in jd_text.lower()]
        degree = DEGREE_RE.search(jd_text)
        pos = re.search(FIELD_HINTS["position"], jd_text)
        loc = re.search(FIELD_HINTS["location"], jd_text)
        exp = re.search(r"(\d)\s*年", jd_text)
        return {
            "position": pos.group(1) if pos else "",  # 无岗位标记时不臆测，交给校验节点处理
            "skills": skills[:6],
            "degree": degree.group(1) if degree else "",
            "min_years": int(exp.group(1)) if exp else 0,
            "location": loc.group(2) if loc else "",
        }


class OpenAICompatLLM:
    """OpenAI 兼容真实 API（DashScope/Kimi 等均可）。未配置 KEY 时抛错，由 workflow 转人工。"""

    def __init__(self):
        self.key = os.environ.get("LLM_API_KEY", "")
        self.base = os.environ.get("LLM_BASE_URL", "https://api.openai.com/v1")
        if not self.key:
            raise RuntimeError("LLM_API_KEY 未配置")

    def extract(self, jd_text: str) -> dict:
        import urllib.request
        req = urllib.request.Request(self.base + "/chat/completions", method="POST")
        req.add_header("Content-Type", "application/json")
        req.add_header("Authorization", "Bearer " + self.key)
        prompt = ("从岗位描述抽取 JSON：{position,skills[],degree,min_years,location}。"
                  "只输出 JSON。岗位描述：\n" + jd_text[:2000])
        body = json.dumps({"model": os.environ.get("LLM_MODEL", "gpt-4o-mini"),
                           "messages": [{"role": "user", "content": prompt}],
                           "response_format": {"type": "json_object"}}).encode()
        with urllib.request.urlopen(req, body, timeout=30) as resp:
            data = json.loads(resp.read().decode())
        return json.loads(data["choices"][0]["message"]["content"])


def get_llm():
    if os.environ.get("LLM_PROVIDER", "mock") == "openai_compatible":
        return OpenAICompatLLM()
    return MockLLM()


# ---------------------------------------------------------------- 节点与编排
@dataclass
class StepResult:
    node: str
    ok: bool
    cost_ms: int = 0
    error: str = ""
    data: dict = field(default_factory=dict)


REQUIRED = {"position": str, "skills": list, "degree": str, "min_years": int, "location": str}


def node_input_clean(raw: str) -> str:
    return re.sub(r"\s+", " ", raw or "").strip()


def node_llm_extract(llm, raw: str) -> dict:
    return llm.extract(raw)


def node_rule_validate(extracted: dict) -> tuple[bool, list]:
    errors = []
    for k, typ in REQUIRED.items():
        v = extracted.get(k)
        if v is None or v == "" or v == []:
            errors.append(f"缺少必填字段 {k}")
        elif typ is int:
            # isinstance(True, int) == True：布尔值会穿透 int 校验，必须显式排除
            if isinstance(v, bool) or not isinstance(v, int):
                errors.append(f"{k} 需为整数")
        elif typ is str:
            # 2026-09 二次审计：真实 LLM 返回畸形 JSON 时，str 字段此前无类型分支，
            # 任何非空值（123/{}/False）都放行，脏数据流入下游分支
            if not isinstance(v, str):
                errors.append(f"{k} 需为字符串")
        elif typ is list:
            # 容器类型本身也要校验：skills="Python"（字符串）会逐字符通过元素检查
            if not isinstance(v, list) or not all(isinstance(x, str) for x in v):
                errors.append(f"{k} 需为字符串数组")
    return (len(errors) == 0), errors


def run_workflow(jd_text: str, max_retry: int = 2) -> dict:
    """执行工作流；JSON 校验失败或 Provider 异常时带错误反馈重试，仍失败转人工确认。

    2026-09 修复：
      1. 重试成功后 status 曾恒为 "retrying"（break 前未复位），现由最终结果推导；
      2. get_llm() 曾在 try 外构造，无 KEY 直接抛出而非转人工，现纳入重试路径
         （异常也计入重试计数，瞬时网络错/429 有机会自愈；生产建议再加指数退避）。
    """
    steps: list[StepResult] = []
    raw = node_input_clean(jd_text)
    steps.append(StepResult("input_clean", True))
    extracted, errors, status = {}, [], "done"
    for attempt in range(max_retry + 1):
        t0 = time.perf_counter()
        try:
            llm = get_llm()
            extracted = node_llm_extract(llm, raw)
            steps.append(StepResult(f"llm_extract#{attempt + 1}", True,
                                    int((time.perf_counter() - t0) * 1000), data=extracted))
        except Exception as exc:  # noqa: BLE001  真实 API 异常也要留存并参与重试
            steps.append(StepResult(f"llm_extract#{attempt + 1}", False,
                                    int((time.perf_counter() - t0) * 1000), str(exc)))
            status = "manual_confirm" if attempt == max_retry else "retrying"
            if attempt < max_retry:
                # 指数退避：0.5s → 1s，对 429/网络抖动减压（mock 模式不会走此路径）
                time.sleep(0.5 * (2 ** attempt))
            # 清空上一轮校验残留：否则最终返回的 errors/extracted 还是旧一轮结果，
            # 与 status=manual_confirm 的真实原因（Provider 异常）不符
            errors = [f"llm_extract 异常: {exc}"]
            extracted = {}
            continue
        ok, errors = node_rule_validate(extracted)
        steps.append(StepResult(f"rule_validate#{attempt + 1}", ok, error=";".join(errors)))
        if ok:
            status = "done"  # 2026-09 修复：重试成功必须复位为 done
            break
        status = "manual_confirm" if attempt == max_retry else "retrying"
    return {"status": status, "result": extracted, "validation_errors": errors,
            "steps": [s.__dict__ for s in steps]}


if __name__ == "__main__":
    import sys
    sample = sys.argv[1] if len(sys.argv) > 1 else (
        "岗位：Python后端开发工程师。地点：成都。要求：3 年以上经验，本科及以上。"
        "熟悉 Python/MySQL/FastAPI，会 Docker 与 Git 加分。")
    out = run_workflow(sample)
    print(json.dumps(out, ensure_ascii=False, indent=2))
