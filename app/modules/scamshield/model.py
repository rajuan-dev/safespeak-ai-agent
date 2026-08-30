SCAMSHIELD_ANALYSIS_TYPES = {"text", "email", "screenshot", "evidence", "url"}
SCAMSHIELD_STATUSES = {"draft", "submitted", "archived"}
SCAMSHIELD_RISK_LEVELS = {"low", "medium", "high", "critical"}

SCAMSHIELD_ACTIONS = {
    "analyzeText": "scamshield.analyze_text",
    "analyzeEmail": "scamshield.analyze_email",
    "analyzeScreenshot": "scamshield.analyze_screenshot",
    "checkUrl": "scamshield.check_url",
    "redact": "scamshield.redact",
    "generateReportDraft": "scamshield.generate_report_draft",
    "submit": "scamshield.submit",
    "get": "scamshield.get",
}
