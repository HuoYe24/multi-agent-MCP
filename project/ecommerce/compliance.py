import re


PII_PATTERNS = {
    "phone": r"1[3-9]\d{9}",
    "id_card": r"\d{17}[\dXx]",
    "bank_card": r"\d{16,19}",
    "email": r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
}

FORBIDDEN_PROMISES = [
    "一定赔偿",
    "保证赔偿",
    "无条件退款",
    "马上到账",
    "百分百成功",
]


def mask_pii(content: str) -> str:
    masked = str(content or "")

    for pattern in PII_PATTERNS.values():
        def _mask(match):
            text = match.group()
            if len(text) <= 6:
                return "*" * len(text)
            return text[:3] + "*" * (len(text) - 6) + text[-3:]

        masked = re.sub(pattern, _mask, masked)

    return masked


def review_customer_service_response(content: str) -> dict:
    sanitized = mask_pii(content)
    violations = []

    for term in FORBIDDEN_PROMISES:
        if term in sanitized:
            violations.append(f"包含不应由客服直接承诺的表述: {term}")

    return {
        "passed": not violations,
        "violations": violations,
        "sanitized_content": sanitized,
    }
