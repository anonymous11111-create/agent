"""Hook: 记录工具调用日志 + 拦截敏感操作。"""
import json
import os
import sys
import datetime


def main():
    event = os.environ.get("HOOK_EVENT", "")
    tool_name = os.environ.get("HOOK_TOOL_NAME", "")
    tool_input_raw = os.environ.get("HOOK_TOOL_INPUT", "{}")

    # 1. 记录日志
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[Hook] {timestamp} {event}: tool={tool_name}")

    # 2. 拦截敏感工具调用
    blocked_tools = {"task_delete", "delete_task"}
    if tool_name in blocked_tools:
        print(f"[Hook] BLOCKED: {tool_name} 被安全策略拦截", file=sys.stderr)
        sys.exit(1)

    # 3. 拦截危险 SQL（DROP/DELETE/TRUNCATE/ALTER/CREATE）
    if tool_name == "database_query":
        try:
            inp = json.loads(tool_input_raw)
            sql = inp.get("sql", "").upper()
            dangerous_keywords = ["DROP", "DELETE", "TRUNCATE", "ALTER", "CREATE"]
            for keyword in dangerous_keywords:
                if keyword in sql:
                    print(
                        f"[Hook] BLOCKED: 检测到危险 SQL 关键字 '{keyword}'",
                        file=sys.stderr,
                    )
                    sys.exit(1)
        except json.JSONDecodeError:
            pass

    # 通过检查，允许执行
    sys.exit(0)


if __name__ == "__main__":
    main()
