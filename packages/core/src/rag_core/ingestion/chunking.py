"""切块策略（基于调研结论：法规按条款等语义边界切分，普通文档段落聚合 + 重叠）。

- 政策法规：识别「第X条」按条款切块，超长条款再按段落细分
- 普通文档：段落聚合至目标长度，相邻块保留 ~15% 重叠
- 每块头部注入【文号 标题】元数据，提升检索与引用质量
- 长度以字符计（中文 ~1.6 字符/token，目标 800 字符 ≈ 500 token）
"""

import re
from dataclasses import dataclass

TARGET_CHARS = 800
OVERLAP_CHARS = 120
MIN_ARTICLE_COUNT = 3  # 至少识别出 3 条才按条款切，避免误判

_ARTICLE_RE = re.compile(r"(?=第[零一二三四五六七八九十百千0-9]+条)")


@dataclass
class TextChunk:
    seq: int
    content: str

    @property
    def approx_tokens(self) -> int:
        return int(len(self.content) / 1.6)


def _header(doc_title: str, doc_number: str) -> str:
    parts = [p for p in (doc_number, doc_title) if p]
    return f"【{' '.join(parts)}】\n" if parts else ""


def _split_paragraphs(text: str) -> list[str]:
    return [p.strip() for p in re.split(r"\n\s*\n|\n", text) if p.strip()]


def _merge_paragraphs(paragraphs: list[str]) -> list[str]:
    """段落聚合至目标长度，相邻块以上一块尾部作重叠。"""
    blocks: list[str] = []
    current = ""
    for p in paragraphs:
        if current and len(current) + len(p) > TARGET_CHARS:
            blocks.append(current)
            current = current[-OVERLAP_CHARS:] + "\n" + p
        else:
            current = f"{current}\n{p}" if current else p
    if current:
        blocks.append(current)
    return blocks


def chunk_text(text: str, doc_title: str = "", doc_number: str = "") -> list[TextChunk]:
    header = _header(doc_title, doc_number)
    articles = [a.strip() for a in _ARTICLE_RE.split(text) if a.strip()]

    if len(articles) - 1 >= MIN_ARTICLE_COUNT:  # 首段通常是标题/前言
        blocks: list[str] = []
        for article in articles:
            if len(article) > TARGET_CHARS * 2:  # 超长条款按段落细分
                blocks.extend(_merge_paragraphs(_split_paragraphs(article)))
            else:
                blocks.append(article)
    else:
        blocks = _merge_paragraphs(_split_paragraphs(text))

    return [TextChunk(seq=i, content=header + b) for i, b in enumerate(blocks)]
