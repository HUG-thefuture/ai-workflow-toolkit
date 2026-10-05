# -*- coding: utf-8 -*-
"""重试路径与校验边界的防御性测试（2026-09 审计修复回归）。

运行（项目根）：python -m pytest job_workflow/test_retry_paths.py -v
覆盖审计发现的三个盲区：
  1. 重试成功后 status 必须复位 "done"（原 bug：恒为 "retrying"）
  2. Provider 异常（网络错/无 KEY）参与重试计数，最终转人工且错误留存
  3. rule_validate 的 int 校验不再被 bool 穿透（isinstance(True, int) == True）
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import workflow  # noqa: E402
from workflow import run_workflow, node_rule_validate  # noqa: E402


class FlakyLLM:
    """第一次返回缺字段（校验失败触发重试），之后返回完整五字段。"""

    def __init__(self):
        self.calls = 0

    def extract(self, jd_text: str) -> dict:
        self.calls += 1
        if self.calls == 1:
            return {}
        return {"position": "Python工程师", "skills": ["Python"], "degree": "本科",
                "min_years": 3, "location": "成都"}


class BoomLLM:
    def extract(self, jd_text: str) -> dict:
        raise RuntimeError("网络错误 429")


def test_retry_success_resets_status(monkeypatch):
    """重试成功后 status 必须是 done（审计 P1 96：曾恒为 retrying）。"""
    llm = FlakyLLM()
    monkeypatch.setattr(workflow, "get_llm", lambda: llm)
    res = run_workflow("岗位：Python工程师。地点：成都。3 年经验，本科。")
    assert res["status"] == "done", f"重试成功后应复位 done，实际 {res['status']!r}"
    assert res["result"]["position"] == "Python工程师"
    nodes = [s["node"] for s in res["steps"]]
    assert "rule_validate#2" in nodes, f"应经历第二次校验: {nodes}"


def test_llm_exception_retries_then_manual_confirm(monkeypatch):
    """Provider 异常参与重试，最终转人工且每步错误信息留存。"""
    monkeypatch.setattr(workflow, "get_llm", lambda: BoomLLM())
    res = run_workflow("岗位：测试。", max_retry=2)
    assert res["status"] == "manual_confirm"
    extract_steps = [s for s in res["steps"] if s["node"].startswith("llm_extract")]
    assert len(extract_steps) == 3, f"应重试到 max_retry+1 次: {[s['node'] for s in extract_steps]}"
    assert all(not s["ok"] and "网络错误" in s["error"] for s in extract_steps)


def test_get_llm_missing_key_manual_confirm(monkeypatch):
    """无 KEY 时不再向上抛 RuntimeError，而是走重试→转人工（审计 P1 95）。"""
    monkeypatch.setenv("LLM_PROVIDER", "openai_compatible")
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    res = run_workflow("岗位：测试。")
    assert res["status"] == "manual_confirm"
    assert res["steps"][-1]["ok"] is False


def test_rule_validate_bool_does_not_pass_as_int():
    """isinstance(True, int) == True 的坑：布尔不得通过 int 校验（审计 P2 93）。"""
    bad = {"position": "x", "skills": ["a"], "degree": "本科",
           "min_years": True, "location": "成都"}
    ok, errors = node_rule_validate(bad)
    assert not ok and any("min_years" in e for e in errors)
    good = {**bad, "min_years": 3}
    ok2, errors2 = node_rule_validate(good)
    assert ok2 and errors2 == []
