"""LLM 生成（经 LiteLLM，默认 deepseek-chat，后期可切本地模型）。"""

from collections.abc import AsyncIterator

import litellm
from rag_core.settings import get_settings


async def stream_answer(system: str, user: str) -> AsyncIterator[str]:
    s = get_settings()
    resp = await litellm.acompletion(
        model=s.llm_model,
        api_key=s.deepseek_api_key or None,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        stream=True,
    )
    async for chunk in resp:
        delta = chunk.choices[0].delta.content
        if delta:
            yield delta
