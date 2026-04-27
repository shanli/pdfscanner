from __future__ import annotations
import os
import re
from pdfscanner.extractor import Topic


def generate(
    topics: list[Topic],
    output_dir: str,
    filename: str = "highlights.md",
) -> str:
    """Render topics to a Markdown file. Returns the output file path."""
    os.makedirs(output_dir, exist_ok=True)
    lines = ["# PDF Scanner — Highlights Report", ""]

    for t in topics:
        lines += [f"## Topic {t.num}：{t.name}", ""]

        if t.highlights:
            lines += ["### 🔑 重点词汇", ""]
            lines += ["| 词汇 | 词性 | 中文释义 | 用法说明 | 搭配例句 |",
                      "|------|------|----------|----------|----------|"]
            for w in sorted(set(t.highlights)):
                lines.append(f"| **{w}** | — | — | — | — |")
            lines.append("")

        if t.sentences:
            lines += ["### 📝 句子", ""]
            for s in t.sentences:
                en = re.sub(r'[\u4e00-\u9fff].*', '', s).strip(" .•")
                zh_m = re.search(
                    r'[\u4e00-\u9fff][\u4e00-\u9fff\s，。！？、；：\u201c\u201d\u2018\u2019（）\w]*', s
                )
                zh = zh_m.group(0).strip() if zh_m else ""
                if not en:
                    continue
                lines.append(f"- {en}")
                if zh:
                    lines.append(f"  > {zh}")
            lines.append("")

    out_path = os.path.join(output_dir, filename)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"Markdown → {out_path}")
    return out_path
