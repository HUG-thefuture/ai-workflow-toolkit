"""调用本地 Dify 工作流并解析 SSE 流式响应。

用法：
    python dify_workflow_test.py
    python dify_workflow_test.py --target "新能源汽车发展概况" --mode streaming
    python dify_workflow_test.py --mode blocking

API Key 通过环境变量 DIFY_API_KEY 或 --api-key 提供，不写入代码。
"""

import argparse
import json
import os

import requests

STREAMING_MODE = "streaming"
BLOCKING_MODE = "blocking"
WORKFLOW_FINISHED = "workflow_finished"
WORKFLOW_SUCCESS = "succeeded"

DEFAULT_API_KEY = os.getenv("DIFY_API_KEY", "")
DEFAULT_BASE_URL = os.getenv("DIFY_BASE_URL", "http://localhost:8100/v1")


def print_result(outputs: dict) -> None:
    result = outputs.get("output")
    print("----------> 工作流最终输出 <----------")
    if isinstance(result, list):
        for index, part in enumerate(result, start=1):
            print(f"\n===== 第 {index} 部分 =====\n{part}")
    else:
        print(result)


def stream_dify_workflow(
    target: str,
    api_key: str = DEFAULT_API_KEY,
    base_url: str = DEFAULT_BASE_URL,
    username: str = "python_request",
) -> bool:
    url = f"{base_url}/workflows/run"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {
        "inputs": {"target": target},
        "response_mode": STREAMING_MODE,
        "user": username,
    }

    with requests.post(url, headers=headers, json=payload, stream=True, timeout=600) as response:
        if response.status_code != 200:
            print(f"请求失败，状态码: {response.status_code}")
            print(response.text)
            return False

        print("=== 开始接收流式响应 ===")
        for line in response.iter_lines():
            if not line:
                continue
            decoded_line = line.decode("utf-8")
            print(f"decoded_line: {decoded_line[:300]}")

            if not decoded_line.startswith("data: "):
                continue
            try:
                json_data = json.loads(decoded_line[6:])
            except json.JSONDecodeError as error:
                print(f"JSON 解析错误: {error}")
                continue

            if json_data.get("event") != WORKFLOW_FINISHED:
                continue

            data = json_data.get("data", {})
            print("---> 工作流执行完毕 <---")
            if data.get("status") != WORKFLOW_SUCCESS:
                print(f"---> 工作流执行失败: {data.get('error')} <---")
                return False
            print_result(data.get("outputs") or {})
            print(f"elapsed_time={data.get('elapsed_time')}s total_tokens={data.get('total_tokens')}")
            return True
    return False


def run_dify_workflow(
    target: str,
    api_key: str = DEFAULT_API_KEY,
    base_url: str = DEFAULT_BASE_URL,
    username: str = "python_request",
) -> bool:
    url = f"{base_url}/workflows/run"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {
        "inputs": {"target": target},
        "response_mode": BLOCKING_MODE,
        "user": username,
    }

    response = requests.post(url, headers=headers, json=payload, timeout=600)
    if response.status_code != 200:
        print(f"请求失败，状态码: {response.status_code}")
        print(response.text)
        return False

    data = response.json().get("data", {})
    if data.get("status") != WORKFLOW_SUCCESS:
        print(f"---> 工作流执行失败: {data.get('error')} <---")
        return False
    print_result(data.get("outputs") or {})
    print(f"elapsed_time={data.get('elapsed_time')}s total_tokens={data.get('total_tokens')}")
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="调用本地 Dify 工作流")
    parser.add_argument("--target", default="新能源汽车发展概况", help="工作流输入主题")
    parser.add_argument("--mode", choices=[STREAMING_MODE, BLOCKING_MODE], default=STREAMING_MODE)
    parser.add_argument("--api-key", default=DEFAULT_API_KEY)
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    args = parser.parse_args()

    if not args.api_key:
        print("缺少 DIFY_API_KEY，请通过 --api-key 或环境变量提供工作流 API Key。")
        raise SystemExit(2)

    if args.mode == STREAMING_MODE:
        ok = stream_dify_workflow(args.target, args.api_key, args.base_url)
    else:
        ok = run_dify_workflow(args.target, args.api_key, args.base_url)
    raise SystemExit(0 if ok else 1)
