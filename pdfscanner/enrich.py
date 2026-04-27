"""
Vocabulary enrichment via Claude API.
Fills in 词性 / 中文释义 / 用法说明 / 搭配例句 for extracted highlights.
Requires ANTHROPIC_API_KEY env var and: pip install anthropic
"""
from __future__ import annotations
import json
import re


_PROMPT_TMPL = """\
你是雅思词汇专家。以下词汇通过 OCR 从雅思 PDF 中提取，可能存在识别错误（截断、大小写错误、多余标点等）。

参考句子（帮助判断 OCR 错误）：
{sentences}

提取的词汇（可能有 OCR 错误）：
{word_list}

请完成以下任务，以 JSON 格式返回结果：
- key 为原始词汇（保持原样，方便匹配）
- value 包含：
  - "corrected": 修正后的词汇或短语（若无错误则与原文相同）
  - "pos": 词性（中文，如 名词 / 动词 / 形容词 / 副词 / 短语）
  - "meaning": 中文释义（简洁，3-8 字）
  - "usage": 用法说明（中文，10-25 字，说明常见用法或注意事项）
  - "example": 搭配例句（英文短句，5-12 个词）

只返回 JSON，不要其他内容。示例：
{{"dill": {{"corrected": "diligent", "pos": "形容词", "meaning": "勤奋的；认真的", "usage": "常用于描述人的工作态度，可修饰 student / worker 等", "example": "a diligent student who never gives up"}}}}
"""


def enrich_words(
    words: list[str],
    context_sentences: list[str] | None = None,
    model: str = "claude-haiku-4-5-20251001",
) -> dict[str, dict[str, str]]:
    """
    Look up vocabulary info for each word via Claude API.
    Returns {word: {pos, meaning, usage, example}}.
    Falls back to empty strings on any per-word error.
    """
    if not words:
        return {}

    try:
        import anthropic
    except ImportError:
        raise RuntimeError(
            "pip install anthropic  is required for --enrich"
        )

    client = anthropic.Anthropic()
    word_list = "\n".join(f"- {w}" for w in words)
    sentences_block = "\n".join(context_sentences or []) or "（无参考句子）"
    prompt = _PROMPT_TMPL.format(word_list=word_list, sentences=sentences_block)

    response = client.messages.create(
        model=model,
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = response.content[0].text.strip()
    # Strip markdown code fences if present
    raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.MULTILINE).strip()

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {}

    result: dict[str, dict[str, str]] = {}
    for word in words:
        info = data.get(word) or data.get(word.lower().strip(".,;:!?\"'")) or {}
        result[word] = {
            "corrected": info.get("corrected", word),
            "pos":       info.get("pos", ""),
            "meaning":   info.get("meaning", ""),
            "usage":     info.get("usage", ""),
            "example":   info.get("example", ""),
        }
    return result
