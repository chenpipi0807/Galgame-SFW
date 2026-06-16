import json


def scan(text: str, entries: list[dict]) -> list[str]:
    """
    扫描 text，匹配 lorebook entries 的关键词，返回匹配到的 content 列表。
    entries: [{"keywords": [...], "content": "..."}, ...]
    """
    text_lower = text.lower()
    matched = []
    for entry in entries:
        keywords = entry.get("keywords", [])
        if isinstance(keywords, str):
            try:
                keywords = json.loads(keywords)
            except Exception:
                keywords = []
        for kw in keywords:
            if kw.lower() in text_lower:
                matched.append(entry["content"])
                break  # 每个 entry 只注入一次
    return matched


def build_injection(matched_contents: list[str]) -> str:
    """将匹配到的条目拼成注入文本"""
    if not matched_contents:
        return ""
    parts = "\n\n".join(matched_contents)
    return f"\n\n【世界观补充】\n{parts}"
