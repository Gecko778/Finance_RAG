"""评测运行器（M6）：把 dataset.yaml 跑过 /api/v1/retrieval，做轻量自动判分 + 导出人工评审表。

判分（不依赖第三方评测库，先给基线）：
- refusal 用例：检索结果为空 → 视为"应拒答且无误引"通过
- 其余用例：must_cite 关键词命中任一检索片段的来源文件名 → 命中通过；
  并检查 expects 要点是否出现在检索文本中（召回近似）

⚠️ 依赖有效 SiliconFlow key（检索需 embedding+rerank）与已灌库的 testdata 政策。
    key/灌库就绪前本脚本无法产出真实分数——这是 M6 的 key 依赖部分。

用法：
  先登录拿 token 或用 API Key；起 API；灌入 testdata 三份政策到某知识库；然后：
  uv run python scripts/eval/run_eval.py --base http://localhost:8000 --token <JWT> [--kb <kb_id>]

RAGAS 升级：拿到基线后可接入 ragas（faithfulness/answer_relevancy/context_precision），
    需额外装 `ragas` 并配置评审 LLM；此处先用关键词命中作为可离线复核的基线。
"""

import argparse
import json
import sys
from pathlib import Path

import httpx
import yaml

DATASET = Path(__file__).with_name("dataset.yaml")


def load_cases() -> list[dict]:
    return yaml.safe_load(DATASET.read_text(encoding="utf-8"))["cases"]


def run(base: str, token: str, kb: str | None) -> int:
    cases = load_cases()
    headers = {"Authorization": f"Bearer {token}"}
    results = []
    passed = 0
    with httpx.Client(base_url=base, timeout=60) as c:
        for case in cases:
            payload = {"query": case["query"], "top_k": 5}
            if kb:
                payload["kb_ids"] = [kb]
            r = c.post("/api/v1/retrieval", headers=headers, json=payload)
            r.raise_for_status()
            hits = r.json()["results"]
            texts = " ".join(h["content"] for h in hits)
            sources = " ".join(h["citation"]["filename"] for h in hits)

            if case["should_refuse"]:
                ok = len(hits) == 0
                reason = "无检索结果(应拒答)" if ok else f"不应有结果却命中 {len(hits)} 条"
            else:
                cite_ok = (not case["must_cite"]) or (case["must_cite"] in sources)
                recall_ok = any(k in texts for k in str(case["expects"]).split("，"))
                ok = cite_ok and recall_ok
                reason = f"引用命中={cite_ok} 要点召回={recall_ok}"

            passed += ok
            results.append({**case, "hits": len(hits), "pass": ok, "reason": reason})
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
