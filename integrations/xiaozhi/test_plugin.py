"""小智插件 build_context 纯逻辑单测。

插件顶部依赖小智仓库的 config.logger / plugins_func.register，本项目环境无这些模块，
故用 sys.modules stub 后再导入插件文件，测试其响应→引用文本的组织逻辑。
"""

import importlib.util
import sys
import types
from pathlib import Path

PLUGIN = Path(__file__).with_name("search_from_finance_rag.py")


def _load_plugin():
    # stub 小智依赖
    logger_mod = types.ModuleType("config.logger")
    logger_mod.setup_logging = lambda: types.SimpleNamespace(
        bind=lambda **k: types.SimpleNamespace(error=lambda *a, **kw: None)
    )
    config_pkg = types.ModuleType("config")
    config_pkg.logger = logger_mod
    reg_mod = types.ModuleType("plugins_func.register")
    reg_mod.register_function = lambda *a, **k: (lambda f: f)
    reg_mod.ToolType = types.SimpleNamespace(SYSTEM_CTL="system_ctl")
    reg_mod.Action = types.SimpleNamespace(REQLLM="reqllm", RESPONSE="response")
    reg_mod.ActionResponse = lambda *a: a
    pf_pkg = types.ModuleType("plugins_func")
    pf_pkg.register = reg_mod
    for name, mod in {
        "config": config_pkg, "config.logger": logger_mod,
        "plugins_func": pf_pkg, "plugins_func.register": reg_mod,
    }.items():
        sys.modules.setdefault(name, mod)

    spec = importlib.util.spec_from_file_location("search_from_finance_rag", PLUGIN)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


plugin = _load_plugin()


def test_build_context_with_citations():
    results = [
        {"content": "第一条 起征点为季度30万元。",
         "citation": {"filename": "起征点公告.docx", "doc_number": "公告2026年第4号"}},
        {"content": "第二条 自然人出租不动产……",
         "citation": {"filename": "起征点公告.docx", "doc_number": ""}},
    ]
    text = plugin.build_context(results, "起征点是多少")
    assert "关于问题【起征点是多少】" in text
    assert "[1] 来源：公告2026年第4号 起征点公告.docx" in text
    assert "[2] 来源：起征点公告.docx" in text  # 无文号时只显文件名
    assert "季度30万元" in text
    assert "注明来源" in text


def test_build_context_empty():
    text = plugin.build_context([], "企业所得税税率")
    assert "没有找到相关政策依据" in text


def test_build_context_caps_at_five():
    results = [{"content": f"第{i}条", "citation": {"filename": "x"}} for i in range(8)]
    text = plugin.build_context(results, "q")
    assert text.count("来源：") == 5  # 最多取前 5 条
