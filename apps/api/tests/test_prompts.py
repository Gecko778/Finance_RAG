"""财税系统提示词单测。"""

from rag_api.prompts import NO_CONTEXT_SYSTEM, build_system_prompt


def test_no_context_returns_refusal_prompt():
    assert build_system_prompt([]) == NO_CONTEXT_SYSTEM
    assert "未检索到" in NO_CONTEXT_SYSTEM


def test_contexts_numbered_and_rules_present():
    prompt = build_system_prompt(["资料A", "资料B"])
    assert "[1] 资料A" in prompt
    assert "[2] 资料B" in prompt
    # 关键财税规则在位
    assert "只使用【检索资料】" in prompt
    assert "财税人员复核" in prompt
    assert "知识库中未找到相关依据" in prompt
