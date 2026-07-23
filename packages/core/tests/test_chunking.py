"""切块策略单元测试（纯函数，无外部依赖）。"""

from rag_core.ingestion.chunking import OVERLAP_CHARS, TARGET_CHARS, chunk_text

POLICY_TEXT = """财政部 税务总局关于小微企业税收优惠的公告

第一条 为支持小微企业发展，对月销售额10万元以下的增值税小规模纳税人，免征增值税。

第二条 对小型微利企业年应纳税所得额不超过100万元的部分，减按25%计入应纳税所得额。

第三条 本公告所称小型微利企业，是指从事国家非限制和禁止行业的企业。

第四条 本公告自2023年1月1日起执行。
"""


def test_policy_split_by_article():
    chunks = chunk_text(POLICY_TEXT, doc_title="小微企业税收优惠公告", doc_number="财税〔2023〕1号")
    # 前言 + 四条 = 5 块
    assert len(chunks) == 5
    # 每块带元数据头
    assert all(c.content.startswith("【财税〔2023〕1号 小微企业税收优惠公告】") for c in chunks)
    # 条款边界正确
    assert "第一条" in chunks[1].content and "第二条" not in chunks[1].content
    assert chunks[4].content.count("第四条") == 1
    # seq 连续
    assert [c.seq for c in chunks] == [0, 1, 2, 3, 4]


def test_plain_text_merge_with_overlap():
    paragraphs = [f"这是第{i}段。" + "内容" * 100 for i in range(10)]  # 每段 ~205 字符
    chunks = chunk_text("\n\n".join(paragraphs))
    assert len(chunks) > 1
    # 块长受控（目标 + 重叠上限的宽松界）
    assert all(len(c.content) <= TARGET_CHARS + OVERLAP_CHARS + 210 for c in chunks)
    # 相邻块有重叠：后块开头包含前块尾部内容
    tail = chunks[0].content[-OVERLAP_CHARS:]
    assert tail[:40] in chunks[1].content


def test_few_articles_fallback_to_paragraph():
    text = "第一条 只有一条的文本。\n\n" + "普通段落。" * 50
    chunks = chunk_text(text)
    assert len(chunks) >= 1  # 未触发条款切分（少于 3 条），走段落聚合


def test_no_header_when_no_metadata():
    chunks = chunk_text("普通文本内容")
    assert not chunks[0].content.startswith("【")
