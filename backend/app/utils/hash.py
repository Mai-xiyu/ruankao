import hashlib
import json
import re
import unicodedata


PUNCTUATION_MAP = str.maketrans(
    {
        "（": "(",
        "）": ")",
        "【": "[",
        "】": "]",
        "［": "[",
        "］": "]",
        "｛": "{",
        "｝": "}",
        "，": ",",
        "。": ".",
        "：": ":",
        "；": ";",
        "？": "?",
        "！": "!",
        "、": ",",
        "“": '"',
        "”": '"',
        "‘": "'",
        "’": "'",
        "－": "-",
        "—": "-",
        "～": "~",
    }
)


def normalize_text(text: str) -> str:
    if text is None:
        return ""
    normalized = unicodedata.normalize("NFKC", str(text))
    normalized = normalized.translate(PUNCTUATION_MAP)
    normalized = normalized.casefold()
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.strip()


def question_hash(stem: str, options: dict | None = None) -> str:
    normalized_options = ""
    if options:
        normalized_options = json.dumps(
            {normalize_text(str(k)): normalize_text(str(v)) for k, v in sorted(options.items())},
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    payload = f"{normalize_text(stem)}|{normalized_options}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()

