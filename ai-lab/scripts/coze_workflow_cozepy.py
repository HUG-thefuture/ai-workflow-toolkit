"""按官方 cozepy 示例流式调用 Coze 工作流（适配本地 Coze Studio）。

原实验使用 COZE_CN_BASE_URL；本地部署时改为 http://127.0.0.1:8888。
"""

import os
import sys

from cozepy import Coze, Stream, TokenAuth, WorkflowEvent, WorkflowEventType

API_KEY = os.getenv("COZE_API_KEY", "")
WORKFLOW_ID = os.getenv("COZE_WORKFLOW_ID", "7699310153518022656")
BASE_URL = os.getenv("COZE_BASE_URL", "http://127.0.0.1:8888")
TARGET = sys.argv[1] if len(sys.argv) > 1 else "新能源汽车发展概况"


def handle_workflow_iterator(stream: Stream[WorkflowEvent]) -> str:
    parts: list[str] = []
    for event in stream:
        if event.event == WorkflowEventType.MESSAGE:
            content = event.message.content
            parts.append(content)
            print(content, end="", flush=True)
        elif event.event == WorkflowEventType.ERROR:
            print(f"\n[error] {event.error}")
        elif event.event == WorkflowEventType.DONE:
            print("\n[done]")
    return "".join(parts)


def main() -> int:
    if not API_KEY:
        print("请通过环境变量 COZE_API_KEY 提供个人访问令牌")
        return 2
    coze = Coze(auth=TokenAuth(token=API_KEY), base_url=BASE_URL)
    stream = coze.workflows.runs.stream(
        workflow_id=WORKFLOW_ID,
        parameters={"target": TARGET},
    )
    text = handle_workflow_iterator(stream)
    print(f"\n共输出 {len(text)} 字")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
