"""小智机器人插件：从财税 RAG 知识库检索（对接本项目 /api/v1/retrieval）。

安装：复制本文件到
  xiaozhi-esp32-server/main/xiaozhi-server/plugins_func/functions/
并在 config.yaml 的 plugins.search_from_finance_rag 配置 base_url / api_key(kb 检索专用 API Key) /
kb_ids(可选) / top_k，再把 search_from_finance_rag 加入 Intent.function_call 的 functions 列表。

与 search_from_ragflow 的差异：
- 响应结构为 {"results":[{"content","score","citation"}]}（本项目形态，非 RAGFlow）
- 认证用 X-API-Key 头（本项目 API Key 走此头；Bearer 会被当 JWT 解析）
"""

import json

import requests
from config.logger import setup_logging
from plugins_func.register import Action, ActionResponse, ToolType, register_function

TAG = __name__
logger = setup_logging()

SEARCH_FROM_FINANCE_RAG_FUNCTION_DESC = {
    "type": "function",
    "function": {
        "name": "search_from_finance_rag",
        "description": "从财税知识库中查询税法政策、申报流程、财税实务等信息",
        "parameters": {
            "type": "object",
            "properties": {
                "question": {"type": "string", "description": "用户的财税相关问题"}
            },
            "required": ["question"],
        },
    },
}


def build_context(results: list[dict], question: str) -> str:
    """把 /retrieval 的 results 组织成带出处的引用文本（纯逻辑，可单测）。"""
    blocks = []
    for i, item in enumerate(results[:5], start=1):
        content = item.get("content", "")
        if not content:
            continue
        cite = item.get("citation", {}) or {}
        src = cite.get("filename", "")
        doc_no = cite.get("doc_number", "")
        label = " ".join(x for x in (doc_no, src) if x)
        header = f"[{i}] 来源：{label}" if label else f"[{i}]"
        blocks.append(f"{header}\n{content}")

    if not blocks:
        return "根据财税知识库查询结果，没有找到相关政策依据。"
    text = f"# 关于问题【{question}】从财税知识库查到以下依据\n"
    text += "\n\n".join(blocks)
    text += "\n\n（回答请依据以上内容并注明来源；如依据不足请如实说明。）"
    return text


@register_function(
    "search_from_finance_rag", SEARCH_FROM_FINANCE_RAG_FUNCTION_DESC, ToolType.SYSTEM_CTL
)
def search_from_finance_rag(conn, question=None):
    question = question if isinstance(question, str) and question else str(question or "")

    cfg = conn.config.get("plugins", {}).get("search_from_finance_rag", {})
    base_url = cfg.get("base_url", "").rstrip("/")
    api_key = cfg.get("api_key", "")
    kb_ids = cfg.get("kb_ids") or None
    top_k = cfg.get("top_k", 5)

    if not base_url or not api_key:
        return ActionResponse(
            Action.RESPONSE, None, "财税知识库未配置（缺少 base_url 或 api_key）"
        )

    payload = {"query": question, "top_k": top_k}
    if kb_ids:
        payload["kb_ids"] = kb_ids
    headers = {"X-API-Key": api_key, "Content-Type": "application/json"}

    try:
        resp = requests.post(
            f"{base_url}/api/v1/retrieval", json=payload, headers=headers, timeout=8
        )
        resp.encoding = "utf-8"
        if resp.status_code == 401:
            return ActionResponse(Action.RESPONSE, None, "财税知识库鉴权失败：API Key 无效或已吊销")
        if resp.status_code == 403:
            msg = "财税知识库无检索权限（API Key 的 scope 需含 retrieval）"
            return ActionResponse(Action.RESPONSE, None, msg)
        resp.raise_for_status()
        results = json.loads(resp.text).get("results", [])
        return ActionResponse(Action.REQLLM, build_context(results, question), None)

    except requests.exceptions.RequestException as e:
        logger.bind(tag=TAG).error(f"财税RAG检索失败：{type(e).__name__}：{e}")
        return ActionResponse(Action.RESPONSE, None, "财税知识库暂时无法访问，请稍后再试")
