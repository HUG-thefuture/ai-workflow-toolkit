# -*- coding: utf-8 -*-
"""邮件内容分类与任务创建流程（简历项目二）。

流程：读入模拟邮件 → 分类（通知/面试/待办/普通）→ 抽取日期与任务 → JSON 字段校验
（失败重试一次）→ 与已有任务去重 → 输出结构化结果。零第三方依赖、确定性规则可复现；
真实场景把 classify/extract 换成 LLM API 调用即可（接口保持不变）。
"""
import json
import re
from pathlib import Path

BASE = Path(__file__).resolve().parent
DATE_RE = re.compile(r"(\d{1,2}月\d{1,2}日|\d{4}-\d{2}-\d{2}|\d{1,2}:\d{2})")

RULES = [
    ("面试", ["面试", "笔试", "offer 沟通", "复试"]),
    ("待办", ["请提交", "请于", "截止", "务必", "需要你"]),
    ("通知", ["通知", "公告", "兹定于", "例行"]),
]


def classify(subject: str, body: str) -> str:
    text = subject + body
    for cat, kws in RULES:
        if any(k in text for k in kws):
            return cat
    return "普通"


def extract(subject: str, body: str, category: str) -> dict:
    date = DATE_RE.search(body)
    task = ""
    if category == "面试":
        task = f"参加「{subject}」相关面试，携带简历与证件"
    elif category == "待办":
        task = re.sub(r"(请|务必|需要你)", "", re.sub(r"\s+", " ", body))[:40]
    result = {"subject": subject, "category": category,
              "task": task if task else None,
              "due": date.group(1) if date and category in ("面试", "待办") else None}
    ok = result["task"] is not None if category in ("面试", "待办") else result["task"] is None
    return {**result, "valid": ok}


def dedup_check(new: dict, existing: list[dict]) -> dict:
    """意图签名判重：类别 + 截止时间相同视为重复任务（文本改写不影响识别）。

    2026-09 修复：due=None 时两封内容完全不同的邮件会因签名相等被误判重复，
    任务静默丢失 —— due 为 None 的邮件不参与判重。
    """
    if (new["task"] and new["due"] is not None
            and any(x["category"] == new["category"] and x.get("due") == new["due"]
                    for x in existing if x["created"])):
        return {**new, "duplicate": True, "created": False}
    if new["task"]:
        return {**new, "duplicate": False, "created": True}
    return {**new, "duplicate": False, "created": False}


MAILS = [
    {"subject": "XX公司面试邀请", "body": "您已通过简历筛选，请于 3月18日 14:00 参加现场面试，携带简历。"},
    {"subject": "月度考核通知", "body": "兹定于本月底进行例行考核，请留意安排。"},
    {"subject": "材料提交提醒", "body": "请于 2026-03-25 前提交实习协议扫描件，务必完成。"},
    {"subject": "周末活动回顾", "body": "上周社团活动圆满结束，感谢参与。"},
    {"subject": "复试通知（时间更正）", "body": "请于 3月18日 参加复试，地点不变。"},
]


def main():
    existing: list[dict] = []
    out = []
    for m in MAILS:
        cat = classify(m["subject"], m["body"])
        r = extract(m["subject"], m["body"], cat)
        if not r["valid"]:  # 校验失败重试一次（模拟 LLM 输出不稳时的重试路径）
            r = extract(m["subject"], m["body"] + " 请于本周完成", cat)
        r = dedup_check(r, existing)
        if r["created"]:
            existing.append(r)
        out.append(r)
        print(f"[{r['category']}] {r['subject']} → 任务:{r['task'] or '—'} 截止:{r['due'] or '—'} "
              f"创建:{r['created']} 重复:{r['duplicate']}")
    (BASE / "classify_result.json").write_text(json.dumps(out, ensure_ascii=False, indent=2),
                                               encoding="utf-8")
    assert out[0]["created"] and out[4]["duplicate"], "同日面试邮件应被意图判重拦截"
    assert out[1]["task"] is None and out[3]["category"] == "普通"
    print(f"分类 {len(out)} 封，创建 {sum(x['created'] for x in out)} 个任务，判重拦截 "
          f"{sum(x['duplicate'] for x in out)} 个 → classify_result.json")


if __name__ == "__main__":
    main()
