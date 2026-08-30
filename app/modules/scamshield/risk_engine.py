import re
from typing import Any
from urllib.parse import urlparse

PHISHING_PATTERNS = {
    "urgent pressure": (r"\b(urgent|immediately|final notice|act now|last chance)\b", 14),
    "credential request": (
        r"\b(password|otp|one[- ]time code|verification code|login code)\b",
        18,
    ),
    "payment request": (
        r"\b(pay|payment|transfer|wire|gift card|crypto|bitcoin|bank account)\b",
        18,
    ),
    "official impersonation": (
        r"\b(bank|paypal|apple|microsoft|ato|government|police|court)\b",
        12,
    ),
    "link in message": (r"https?://|www\.", 10),
    "remote access request": (r"\b(anydesk|teamviewer|remote access|screen share)\b", 14),
    "delivery or toll lure": (r"\b(parcel|delivery|toll|postage|customs fee)\b", 10),
}

EMAIL_HEADER_PATTERNS = {
    "spf failed": r"\bspf\b.{0,20}\bfail",
    "dkim failed": r"\bdkim\b.{0,20}\bfail",
    "dmarc failed": r"\bdmarc\b.{0,20}\bfail",
}

SUSPICIOUS_TLDS = {"zip", "top", "click", "work", "shop", "xyz"}


def _add_unique(target: list[str], value: str) -> None:
    if value not in target:
        target.append(value)


def extract_entities(content: str) -> dict[str, Any]:
    urls = re.findall(r"https?://[^\s]+", content, flags=re.IGNORECASE)
    emails = re.findall(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", content, flags=re.IGNORECASE)
    phones = re.findall(r"\+?\d[\d\s().-]{7,}\d", content)
    amounts = re.findall(
        r"\b(?:AUD|USD|GBP|EUR)\s?\d[\d,]*(?:\.\d{2})?\b|[$€£]\s?\d[\d,]*(?:\.\d{2})?\b",
        content,
        flags=re.IGNORECASE,
    )
    organizations = re.findall(
        r"\b(?:PayPal|Apple|Microsoft|ATO|Centrelink|Amazon|NAB|ANZ|Westpac|CommBank)\b",
        content,
        flags=re.IGNORECASE,
    )
    transaction_ids = re.findall(
        r"\b(?:transaction(?:\s+id)?|txn|txid|receipt|remittance)\s*[:#-]?\s*([A-Z0-9-]{6,})\b",
        content,
        flags=re.IGNORECASE,
    )
    primary_domain = None
    if urls:
        parsed = urlparse(urls[0])
        primary_domain = parsed.hostname
    return {
        "urls": urls,
        "emailAddresses": emails,
        "phoneNumbers": phones,
        "amounts": amounts,
        "organizations": list(dict.fromkeys(organizations)),
        "transactionIds": transaction_ids,
        "primaryUrlDomain": primary_domain,
    }


def analyze_sender_profile(email_input: dict[str, Any]) -> dict[str, Any]:
    sender = (email_input.get("from") or "").strip()
    headers = email_input.get("headers") or {}
    header_blob = " ".join(f"{key}: {value}" for key, value in headers.items())
    signals: list[str] = []
    for label, pattern in EMAIL_HEADER_PATTERNS.items():
        if re.search(pattern, header_blob, flags=re.IGNORECASE):
            signals.append(label)
    reply_to = None
    for key, value in headers.items():
        if str(key).lower() == "reply-to":
            reply_to = str(value)
            break
    return {
        "possibleSender": sender or None,
        "replyTo": reply_to,
        "spf": "failed" if "spf failed" in signals else "unknown",
        "dkim": "failed" if "dkim failed" in signals else "unknown",
        "dmarc": "failed" if "dmarc failed" in signals else "unknown",
        "signals": signals,
    }


def analyze_url_reputation(url: str) -> dict[str, Any]:
    hostname = (urlparse(url).hostname or "").lower()
    signals: list[str] = []
    if hostname.count("-") >= 2:
        signals.append("multiple-hyphen-domain")
    if any(char.isdigit() for char in hostname):
        signals.append("numeric-domain-pattern")
    tld = hostname.rsplit(".", 1)[-1] if "." in hostname else ""
    if tld in SUSPICIOUS_TLDS:
        signals.append("high-risk-tld")
    return {
        "domain": hostname or None,
        "signals": signals,
        "ipGeolocation": None,
        "domainAgeDays": None,
    }


def risk_level_for_score(score: int) -> str:
    if score >= 75:
        return "critical"
    if score >= 50:
        return "high"
    if score >= 25:
        return "medium"
    return "low"


def build_summary(risk_level: str, indicators: list[str]) -> str:
    if indicators:
        return (
            f"This content shows {risk_level} scam risk based on signals such as "
            f"{', '.join(indicators[:3])}."
        )
    return "No strong automated scam markers were detected in the provided content."


def score_content(
    content: str,
    *,
    analysis_type: str,
    email_input: dict[str, Any] | None = None,
    url_value: str | None = None,
) -> dict[str, Any]:
    lowered = content.lower()
    indicators: list[str] = []
    red_flags: list[str] = []
    recommendations: list[str] = []
    score = 0
    for label, (pattern, weight) in PHISHING_PATTERNS.items():
        if re.search(pattern, lowered, flags=re.IGNORECASE):
            _add_unique(indicators, label)
            _add_unique(red_flags, f"Detected {label}.")
            score += weight
    entities = extract_entities(content)
    if entities["amounts"]:
        score += 7
    if entities["transactionIds"]:
        score += 4
    if entities["urls"] and "link in message" not in indicators:
        _add_unique(indicators, "link in message")
        _add_unique(red_flags, "Detected link in message.")
        score += 10
    sender_analysis = analyze_sender_profile(email_input or {}) if email_input else None
    if sender_analysis and sender_analysis["signals"]:
        for signal in sender_analysis["signals"]:
            _add_unique(indicators, signal)
            _add_unique(red_flags, f"Sender analysis flagged: {signal}.")
            score += 12
    url_reputation = analyze_url_reputation(url_value or entities.get("urls", [""])[0]) if (
        analysis_type == "url" or entities["urls"]
    ) else None
    if url_reputation and url_reputation["signals"]:
        for signal in url_reputation["signals"]:
            _add_unique(indicators, signal)
            _add_unique(red_flags, f"URL analysis flagged: {signal}.")
            score += 10
    score = max(0, min(100, score))
    risk_level = risk_level_for_score(score)
    recommendations.extend(
        [
            "Do not click links, share codes, send money, or provide personal "
            "details until verified.",
            "Use a trusted phone number, official website, or official app to check the request.",
            "Keep screenshots and message details in case you need to report the incident.",
        ]
    )
    confidence = "high" if score >= 60 else "medium" if score >= 25 else "low"
    return {
        "riskScore": score,
        "riskLevel": risk_level,
        "confidence": confidence,
        "confidenceScore": round(min(0.95, 0.35 + len(indicators) * 0.08), 2),
        "summary": build_summary(risk_level, indicators),
        "indicators": indicators,
        "redFlags": red_flags,
        "recommendations": recommendations,
        "extractedEntities": entities,
        "urlReputation": url_reputation,
        "senderAnalysis": sender_analysis,
    }
