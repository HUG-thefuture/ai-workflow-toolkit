"""调用本地 Coze Studio 工作流 OpenAPI。

对应实验：Python 调用 Coze 平台工作流。
接口：POST /v1/workflow/run（阻塞）与 /v1/workflow/stream_run（SSE 流式）。
鉴权：Authorization: Bearer <个人访问令牌>。

用法示例：
    python coze_workflow_test.py --workflow-id 7450000000000000000 --target "新能源汽车发展概况"
    python coze_workflow_test.py --mode streaming
"""

import argparse
import json
import os
import sys
import time

import requests

DEFAULT_API_KEY = os.getenv("COZE_API_KEY", "")
DEFAULT_BASE_URL = os.getenv("COZE_BASE_URL", "http://127.0.0.1:8888")
DEFAULT_WORKFLOW_ID = os.getenv("COZE_WORKFLOW_ID", "")


def _headers(api_key: str) -> dict:
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }


def run_coze_workflow(
    workflow_id: str,
    target: str,
    api_key: str = DEFAULT_API_KEY,
    base_url: str = DEFAULT_BASE_URL,
    timeout: int = 300,
) -> dict:
    """阻塞模式：POST /v1/workflow/run。"""
    url = f"{base_url.rstrip('/')}/v1/workflow/run"
    payload = {
        "workflow_id": str(workflow_id),
        "parameters": {"target": target},
    }
    started = time.time()
    resp = requests.post(url, headers=_headers(api_key), json=payload, timeout=timeout)
    resp.raise_for_status()
    result = resp.json()
    elapsed = time.time() - started

    if result.get("code") != 0:
        print(f"工作流执行失败: code={result.get('code')} msg={result.get('msg')}")
        return result

    data = result.get("data")
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except json.JSONDecodeError:
            pass
    # 本地 Coze Studio 将文本结果放在 data.data，云端返回 data.output 或纯文本
    if isinstance(data, dict) and isinstance(data.get("data"), str):
        output = data["data"]
    elif isinstance(data, dict) and "output" in data:
        output = data["output"]
    else:
        output = data
    print("---------- 工作流输出 ----------")
    print(output if isinstance(output, str) else json.dumps(output, ensure_ascii=False, indent=2))
    print(f"elapsed={elapsed:.2f}s token={result.get('token')} cost={result.get('cost')}")
    return result


def stream_coze_workflow(
    workflow_id: str,
    target: str,
    api_key: str = DEFAULT_API_KEY,
    base_url: str = DEFAULT_BASE_URL,
    timeout: int = 300,
) -> None:
    """流式模式：POST /v1/workflow/stream_run，逐条打印 SSE 事件。"""
    url = f"{base_url.rstrip('/')}/v1/workflow/stream_run"
    payload = {
        "workflow_id": str(workflow_id),
        "parameters": {"target": target},
    }
    started = time.time()
    text_parts: list[str] = []

    with requests.post(
        url, headers=_headers(api_key), json=payload, stream=True, timeout=timeout
    ) as resp:
        resp.raise_for_status()
        event_type = "message"
        for raw in resp.iter_lines(decode_unicode=True):
            if raw is None:
                continue
            line = raw.strip()
            if not line:
                continue
            if line.startswith("event:"):
                event_type = line[len("event:"):].strip()
                continue
            if line.startswith("id:") or line.startswith(":"):
                continue
            if not line.startswith("data:"):
                continue
            data_text = line[len("data:"):].strip()
            try:
                event = json.loads(data_text)
            except json.JSONDecodeError:
                print(f"[{event_type}] {data_text}")
                continue

            if event_type == "error":
                print(f"[error] {event.get('error_message') or event}")
                break
            if event.get("content"):
                text_parts.append(event["content"])
                print(f"[{event_type}] {event['content']}", end="", flush=True)
            elif event.get("error_message"):
                print(f"\n[{event_type}] error: {event['error_message']}")

    elapsed = time.time() - started
    print()
    print(f"elapsed={elapsed:.2f}s")
    if text_parts:
        print("---------- 汇总输出 ----------")
        print("".join(text_parts))


def main() -> int:
    parser = argparse.ArgumentParser(description="调用本地 Coze Studio 工作流")
    parser.add_argument("--workflow-id", default=DEFAULT_WORKFLOW_ID, help="工作流 ID")
    parser.add_argument("--target", default="新能源汽车发展概况", help="工作流输入参数 target")
    parser.add_argument("--mode", choices=["blocking", "streaming"], default="blocking")
    parser.add_argument("--api-key", default=DEFAULT_API_KEY, help="个人访问令牌（PAT）")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    args = parser.parse_args()

    if not args.api_key:
        print("缺少 COZE_API_KEY，请通过 --api-key 或环境变量提供个人访问令牌。")
        return 2
    if not args.workflow_id:
        print("缺少工作流 ID，请通过 --workflow-id 或环境变量 COZE_WORKFLOW_ID 提供。")
        return 2

    if args.mode == "streaming":
        stream_coze_workflow(args.workflow_id, args.target, args.api_key, args.base_url)
        return 0

    result = run_coze_workflow(args.workflow_id, args.target, args.api_key, args.base_url)
    return 0 if result.get("code") == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
