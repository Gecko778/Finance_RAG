"""评测运行器（M6）：把 dataset.yaml 跑过 /api/v1/chat（真实端到端），判分并导出明细。

判分（基于真实生成答案，而非仅检索层）：
- refusal 用例：答案包含"未找到/没有找到/未涉及/无相关依据"等 → 正确拒答通过
- 其余用例：答案命中 expects 要点关键词（按"，"切分，任一命中）→ 通过；
  若指定 must_cite，则要求引用来源文件名含该关键词

依赖有效 SiliconFlow key（检索/rerank）+ DeepSeek key（生成）+ 已灌库。

用法：
  uv run python scripts/eval/run_eval.py --base http://localhost:8000 --token <JWT> [--kb <kb_id>]
"""

import argparse
import json
import sys
from pathlib import Path

import httpx
import yaml

DATASET = Path(__file__).with_name("dataset.yaml")
REFUSAL_MARKERS = ("未找到", "没有找到", "未涉及", "无相关", "未包含", "无法回答")


def load_cases() -> list[dict]:
    return yaml.safe_load(DATASET.read_text(encoding="utf-8"))["cases"]


def _chat(client: httpx.Client, token: str, query: str, kb: str | None) -> tuple[str, list[dict]]:
    """调用 /chat SSE，返回 (答案文本, 引用列表)。"""
    payload: dict = {"query": query, "top_k": 5}
    if kb:
        payload["kb_ids"] = [kb]
    answer, citations = "", []
    with client.stream(
        "POST", "/api/v1/chat", headers={"Authorization": f"Bearer {token}"}, json=payload
    ) as resp:
        resp.raise_for_status()
        event = ""
        for line in resp.iter_lines():
            if line.startswith("event:"):
                event = line[6:].strip()
            elif line.startswith("data:"):
                data = json.loads(line[5:].strip())
                if event == "citations":
                    citations = data.get("citations", [])
                elif event == "token":
                    answer += data.get("text", "")
    return answer, citations


def run(base: str, token: str, kb: str | None) -> int:
    cases = load_cases()
    results, passed = [], 0
    with httpx.Client(base_url=base, timeout=120) as c:
        for case in cases:
            answer, citations = _chat(c, token, case["query"], kb)
            sources = " ".join(x.get("filename", "") for x in citations)
            refused = any(m in answer for m in REFUSAL_MARKERS)

            if case["should_refuse"]:
                ok = refused
                reason = "正确拒答" if ok else "未拒答（应拒答却作答）"
            else:
                recall = any(k in answer for k in str(case["expects"]).split("，"))
                cite_ok = (not case["must_cite"]) or (case["must_cite"] in sources)
                ok = recall and cite_ok and not refused
                reason = f"要点命中={recall} 引用={cite_ok} 误拒答={refused}"

            passed += ok
            results.append({**case, "answer": answer, "pass": ok, "reason": reason})
            print(f"[{'PASS' if ok else 'FAIL'}] {case['id']} {case['category']}: {reason}")

    out = Path(__file__).with_name("eval_result.json")
    out.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n基线：{passed}/{len(cases)} 通过；明细写入 {out.name}")
    return 0 if passed == len(cases) else 1


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--base", default="http://localhost:8000")
    p.add_argument("--token", required=True, help="JWT（登录获取）")
    p.add_argument("--kb", default=None, help="限定知识库 id（可选）")
    args = p.parse_args()
    sys.exit(run(args.base, args.token, args.kb))
