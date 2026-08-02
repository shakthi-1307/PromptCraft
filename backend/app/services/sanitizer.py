import re
from app.logger import get_logger

log = get_logger(__name__)

# Patterns that indicate prompt injection attempts
INJECTION_PATTERNS = [
    # Instruction overrides
    r"ignore\s+(all\s+)?(previous|prior|above|earlier)\s+instructions?",
    r"disregard\s+(all\s+)?(previous|prior|above|earlier)\s+instructions?",
    r"forget\s+(all\s+)?(previous|prior|above|earlier)\s+instructions?",
    r"override\s+(all\s+)?instructions?",
    r"do\s+not\s+follow\s+(your\s+)?instructions?",

    # Role hijacking
    r"you\s+are\s+now\s+(a|an|the)\s+\w+",
    r"act\s+as\s+(a|an|the)\s+\w+",
    r"pretend\s+(you\s+are|to\s+be)\s+(a|an|the)?\s*\w+",
    r"roleplay\s+as\s+(a|an|the)?\s*\w+",
    r"from\s+now\s+on\s+(you\s+are|act\s+as)",
    r"your\s+new\s+(role|persona|identity)\s+is",

    # System prompt extraction
    r"(reveal|show|print|output|display|repeat|tell me)\s+(your\s+)?(system\s+)?(prompt|instructions?|context)",
    r"what\s+(are|were)\s+your\s+(original\s+)?instructions?",
    r"(ignore|bypass)\s+(your\s+)?(safety|content)\s+(filters?|guidelines?|rules?)",

    # Jailbreak keywords
    r"\bDAN\b",
    r"developer\s+mode",
    r"jailbreak",
    r"no\s+restrictions?",
    r"without\s+(any\s+)?(restrictions?|limitations?|filters?)",
    r"(disable|remove)\s+(your\s+)?(safety|content)\s+(filters?|guidelines?)",

    # Prompt boundary attacks
    r"---+\s*(system|user|assistant)\s*:?",
    r"<\s*(system|user|assistant)\s*>",
    r"\[\s*(system|user|assistant|inst)\s*\]",
    r"#{3,}\s*(system|instruction)",
]

COMPILED_PATTERNS = [re.compile(p, re.IGNORECASE) for p in INJECTION_PATTERNS]


def check_injection(text: str) -> tuple[bool, str]:
    """
    Returns (is_safe, reason).
    is_safe=True means clean input, is_safe=False means injection detected.
    """
    normalized = " ".join(text.lower().split())

    for pattern in COMPILED_PATTERNS:
        match = pattern.search(normalized)
        if match:
            log.warning(f"Prompt injection detected | pattern: '{pattern.pattern}' | matched: '{match.group()}'")
            return False, f"Suspicious pattern detected: '{match.group()}'"

    return True, ""


def sanitize_input(text: str) -> str:
    """
    Strip characters commonly used for prompt boundary injection.
    Keeps the input readable while removing structural attack vectors.
    """
    # Remove zero-width characters
    text = re.sub(r"[\u200b\u200c\u200d\ufeff]", "", text)
    # Collapse multiple dashes (used for prompt boundary attacks like ---)
    text = re.sub(r"-{3,}", "--", text)
    # Collapse multiple hashes
    text = re.sub(r"#{3,}", "##", text)
    return text.strip()