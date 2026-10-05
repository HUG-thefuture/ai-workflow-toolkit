# -*- coding: utf-8 -*-
"""20 份模拟岗位描述回归测试（简历口径）。

断言：
  1. 全部 20 份执行完成，无未捕获异常；
  2. 正常样本 status=done 且五字段齐备；
  3. 空描述样本 status=manual_confirm（转人工）；
  4. 每份都有节点耗时与错误留存（空错误串允许）。
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from workflow import run_workflow

BASE = Path(__file__).resolve().parent


def test_full_regression():
    jobs = sorted((BASE / "data" / "jobs").glob("jd_*.txt"))
    assert len(jobs) == 20, "回归集应有 20 份岗位描述"
    report = []
    for f in jobs:
        res = run_workflow(f.read_text(encoding="utf-8"))
        assert "status" in res and "steps" in res
        for s in res["steps"]:
            assert "cost_ms" in s, "节点耗时必须留存"
        if f.name in ("jd_05.txt", "jd_15.txt"):
            assert res["status"] == "manual_confirm", f"{f.name} 缺岗位/空描述应转人工"
            continue
        assert res["status"] == "done", f"{f.name} 应正常完成: {res['validation_errors']}"
        r = res["result"]
        assert all(r.get(k) not in (None, "", []) for k in
                   ("position", "skills", "degree", "min_years", "location")), f"{f.name} 字段不齐"
        report.append({"file": f.name, "status": res["status"],
                       "position": r["position"], "skills": r["skills"],
                       "nodes": len(res["steps"])})
    assert len(report) == 18
    (BASE / "reports").mkdir(exist_ok=True)
    (BASE / "reports" / "regression_summary.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")


def test_retry_and_manual_confirm_paths():
    from workflow import run_workflow
    res = run_workflow("")  # 空输入 → 抽取结果不完整 → 重试后转人工
    assert res["status"] == "manual_confirm"
    retried = [s for s in res["steps"] if s["node"].startswith("rule_validate")]
    assert len(retried) >= 2, "应至少经历一次校验重试"
    assert any(s["error"] for s in res["steps"]), "错误信息必须留存"


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-v", "--no-header"]))
