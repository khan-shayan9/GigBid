"""Keyword rules that sort jobs into the three persona domains (or "other").

These rules belong to the pipeline only; they are never copied into agent/ prompts or config.
"""

import re

DOMAIN_KEYWORDS: dict[str, list[str]] = {
    "ai_ml": [
        "machine learning", "deep learning", "artificial intelligence", "ai", "ml", "llm",
        "nlp", "computer vision", "chatbot", "pytorch", "tensorflow", "langchain", "openai",
        "gpt", "neural network", "data scientist", "data science", "rag",
    ],
    "data": [
        "data analysis", "data analyst", "data analytics", "data visualization", "power bi",
        "tableau", "dashboard", "excel", "sql", "looker", "google sheets", "statistics",
        "business intelligence",
    ],
    "web": [
        "web development", "web developer", "full stack", "full-stack", "frontend", "front-end",
        "backend", "back-end", "react", "next.js", "node.js", "django", "laravel", "vue",
        "javascript", "typescript", "php", "web app", "web application",
    ],
}
DOMAINS = list(DOMAIN_KEYWORDS)  # precedence order: first match wins

_PATTERNS = {
    domain: re.compile(
        r"\b(" + "|".join(re.escape(word) for word in words) + r")s?\b", re.IGNORECASE
    )
    for domain, words in DOMAIN_KEYWORDS.items()
}


def classify_domain(text: str) -> str:
    for domain in DOMAINS:
        if _PATTERNS[domain].search(text):
            return domain
    return "other"
