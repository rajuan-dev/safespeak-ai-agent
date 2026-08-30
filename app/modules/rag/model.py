from typing import Literal

RAG_SOURCE_STATUSES = [
    "draft",
    "pending_review",
    "approved",
    "rejected",
    "expired",
    "archived",
]
RAG_SOURCE_CATEGORIES = [
    "internal_product_rule",
    "official_legal_source",
    "official_support_source",
    "admin_content",
]
RAG_STATE_OR_TERRITORIES = [
    "AU",
    "NSW",
    "VIC",
    "QLD",
    "WA",
    "SA",
    "TAS",
    "ACT",
    "NT",
    "FEDERAL",
]
RAG_LEGAL_DOMAINS = [
    "criminal_law",
    "civil_law",
    "discrimination",
    "workplace",
    "domestic_family_violence",
    "online_safety",
    "scam_fraud",
    "privacy",
    "migration",
    "housing",
    "consumer",
    "police_reporting",
    "support_service",
    "other",
]
RAG_PATHWAY_CATEGORIES = [
    "reporting",
    "support",
    "legal_information",
    "evidence_guidance",
    "safety_planning",
    "scam_response",
    "workplace_options",
    "online_abuse",
    "domestic_family_violence",
    "other",
]
RAG_SOURCE_RELIABILITIES = ["official", "trusted_partner", "internal", "unknown"]
RAG_REFRESH_CADENCES = ["quarterly", "event_driven", "monthly", "manual"]
RAG_JURISDICTIONS = [
    "Cth",
    "NSW",
    "VIC",
    "QLD",
    "SA",
    "WA",
    "TAS",
    "NT",
    "ACT",
    "AU",
    "Global",
    "Internal",
]
RAG_TOPICS = [
    "discrimination",
    "racial",
    "racial_hatred",
    "online_safety",
    "scam",
    "migrant",
    "privacy",
    "workplace",
    "dv",
    "evidence",
    "support",
    "safespeak_policy",
    "consent",
    "crisis",
    "education",
    "local_intelligence",
    "smart_dialler",
    "other",
]
RAG_SOURCE_TYPES = [
    "Act",
    "Regulation",
    "Guideline",
    "Form",
    "Decision",
    "Report",
    "Policy",
    "ProductRequirement",
    "SupportResource",
    "FAQ",
    "WebPage",
]
RAG_INGESTION_STATUSES = [
    "metadata_only",
    "requires_ocr",
    "ocr_completed",
    "ocr_low_confidence",
    "ocr_failed",
    "pending_ocr_review",
    "ocr_reviewed",
    "fetched",
    "chunked",
    "embedded",
    "partial_index_failed",
    "failed",
]

RAG_ACTIONS = {
    "search": "rag.search",
    "answer": "rag.answer",
    "timelineAssistant": "rag.timeline_assistant",
    "debugRetrieve": "rag.debug_retrieve",
    "sourceCreate": "rag.knowledge_source.create",
    "sourceUpdate": "rag.knowledge_source.update",
    "sourceDelete": "rag.knowledge_source.delete",
    "sourceIngest": "rag.knowledge_source.ingest",
    "sourceRefresh": "rag.knowledge_source.refresh",
    "sourceApprove": "rag.knowledge_source.approve",
    "sourceReject": "rag.knowledge_source.reject",
    "sourceReindex": "rag.knowledge_source.reindex",
    "sourceReadiness": "rag.knowledge_source.readiness",
    "sourceOcrRun": "rag.knowledge_source.ocr.run",
    "sourceOcrApprove": "rag.knowledge_source.ocr.approve",
}

SourceStatus = Literal["draft", "pending_review", "approved", "rejected", "expired", "archived"]
