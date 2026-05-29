import logging
from langchain_core.tools import tool
from langgraph.config import get_config

logger = logging.getLogger(__name__)


@tool
async def database_query(sql: str) -> str:
    """用于在 PostgreSQL 中执行只读查询（SELECT）。接收由模型生成的查询语句，并返回结构化数据结果。该工具仅用于检索数据，严禁任何写入或修改数据库的语句。"""
    try:
        trimmed = sql.strip().upper()
        if not trimmed.startswith("SELECT"):
            return f"错误：仅支持 SELECT 查询语句。提供的 SQL: {sql}"

        config = get_config()
        db_session = config["configurable"]["db_session"]

        from sqlalchemy import text
        result = await db_session.execute(text(sql))
        columns = list(result.keys())
        rows = result.fetchall()

        if not rows:
            return "查询结果为空（无数据）"

        # Format as table
        col_widths = [len(c) for c in columns]
        str_rows = []
        for row in rows:
            str_row = []
            for i, val in enumerate(row):
                s = str(val) if val is not None else "NULL"
                str_row.append(s)
                col_widths[i] = max(col_widths[i], len(s))
            str_rows.append(str_row)

        header = "| " + " | ".join(f"{c:<{col_widths[i]}}" for i, c in enumerate(columns)) + " |"
        separator = "|" + "|".join("-" * (w + 2) for w in col_widths) + "|"
        data_lines = []
        for str_row in str_rows:
            line = "| " + " | ".join(f"{str_row[i]:<{col_widths[i]}}" for i in range(len(columns))) + " |"
            data_lines.append(line)

        output = f"查询结果:\n{header}\n{separator}\n" + "\n".join(data_lines)
        return output
    except Exception as e:
        logger.error("database_query failed: %s", e)
        return f"错误：操作失败 - {e}\nSQL: {sql}"
