# -*- coding: utf-8 -*-
"""email_classifier 单元测试：分类规则 / 抽取校验 / 意图判重。

运行（项目根）：python -m pytest email_classifier/test_classify.py -v
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from classify import classify, extract, dedup_check, MAILS  # noqa: E402


def test_classify_rules_priority():
    assert classify("XX公司面试邀请", "请于 3月18日 参加现场面试") == "面试"
    assert classify("材料提交提醒", "请于 2026-03-25 前提交，务必完成") == "待办"
    assert classify("月度考核通知", "兹定于本月底进行例行考核") == "通知"
    assert classify("周末活动回顾", "上周活动圆满结束") == "普通"


def test_classify_order_matters():
    # 同时命中"面试"与"待办"关键词时，面试规则优先（RULES 顺序）
    assert classify("复试安排", "请于 3月18日 参加复试，务必携带简历") == "面试"


def test_extract_interview_task_and_due():
    r = extract("XX公司面试邀请", "请于 3月18日 14:00 参加现场面试", "面试")
    assert r["valid"] and r["due"] == "3月18日"
    assert "面试" in r["task"]


def test_extract_todo_trims_and_notice_has_no_task():
    r = extract("材料提交提醒", "请于 2026-03-25 前提交扫描件，务必完成", "待办")
    assert r["valid"] and r["due"] == "2026-03-25" and "扫描件" in r["task"]
    r2 = extract("月度考核通知", "兹定于例行考核", "通知")
    assert r2["valid"] and r2["task"] is None and r2["due"] is None


def test_dedup_same_category_and_date():
    new = {"subject": "复试通知", "category": "面试", "task": "参加复试",
           "due": "3月18日", "valid": True}
    existing = [{"category": "面试", "due": "3月18日", "created": True, "task": "参加面试"}]
    assert dedup_check(new, existing)["duplicate"] is True
    different_day = dedup_check({**new, "due": "3月19日"}, existing)
    assert different_day["duplicate"] is False and different_day["created"] is True


def test_dedup_no_due_never_flagged_duplicate():
    """due=None 的两封不同待办邮件不得互判重复（2026-09 审计修复回归：曾静默丢任务）。"""
    first = {"subject": "提交表格", "category": "待办", "task": "交表格", "due": None, "valid": True}
    second = {"subject": "缴学费", "category": "待办", "task": "去缴费", "due": None, "valid": True}
    r1 = dedup_check(first, [])
    assert r1["created"] is True and r1["duplicate"] is False
    r2 = dedup_check(second, [r1])
    assert r2["duplicate"] is False and r2["created"] is True, "无截止时间的不同任务不得判重"


def test_builtin_mails_end_to_end():
    """内置 5 封样例全链路：第 1 封创建任务、第 5 封同日判重拦截。"""
    existing, out = [], []
    for m in MAILS:
        cat = classify(m["subject"], m["body"])
        r = extract(m["subject"], m["body"], cat)
        if not r["valid"]:
            r = extract(m["subject"], m["body"] + " 请于本周完成", cat)
        r = dedup_check(r, existing)
        if r["created"]:
            existing.append(r)
        out.append(r)
    assert out[0]["created"] is True
    assert out[4]["duplicate"] is True      # 同日面试邮件判重
    assert out[1]["task"] is None           # 通知类不产任务
    assert out[3]["category"] == "普通"
