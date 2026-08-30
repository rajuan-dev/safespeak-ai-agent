SUPPORT_ACTIONS = {
    "servicesList": "support.services.list",
    "serviceGet": "support.services.get",
    "recommendations": "support.recommendations",
    "warmReferral": "support.warm_referral",
    "advocatesList": "support.advocates.list",
    "advocateRequest": "support.advocate_request",
    "helpRequest": "support.help_request",
    "safetyPlanList": "support.safety_plan.list",
    "safetyPlanCreate": "support.safety_plan.create",
    "safetyPlanUpdate": "support.safety_plan.update",
}

SUPPORT_SERVICE_TYPES = {
    "counselling",
    "legal_information",
    "housing",
    "financial",
    "crisis",
    "community",
    "health",
    "online_safety",
}
SUPPORT_RESOURCE_TYPES = {
    "emergency",
    "police",
    "government",
    "legal",
    "mental_health",
    "domestic_violence_agency",
    "workplace_body",
    "anti_discrimination_body",
    "council_support",
    "evidence_guidance",
    "safety_planning",
    "scam_support",
    "online_safety",
}
SUPPORT_ISSUE_TYPES = {
    "domestic_violence",
    "workplace_bullying",
    "racism_discrimination",
    "online_abuse",
    "scam_fraud",
    "racial_abuse",
    "migrant_challenges",
    "cyber_scam",
    "theft_property",
    "harassment",
    "mental_health_distress",
    "general_support",
}
SUPPORT_RESOURCE_RISK_LEVELS = {"low", "medium", "high", "immediate", "all"}
SUPPORT_SERVICE_CARD_ICONS = {
    "scale",
    "shield",
    "phone",
    "community",
    "counselling",
    "home",
    "bell",
    "sparkles",
}
SUPPORT_SERVICE_OVERLAY_TONES = {"default", "dark", "blue", "red", "brown", "purple"}
SUPPORT_REQUEST_STATUSES = {"pending", "accepted", "completed", "cancelled"}
ADVOCATE_REQUEST_STATUSES = {
    "pending",
    "matched",
    "contact_initiated",
    "closed",
    "declined",
    "accepted",
    "completed",
    "cancelled",
}
ADVOCATE_VETTING_STATUSES = {"pending", "approved", "rejected", "expired"}
ADVOCATE_OPT_IN_STATUSES = {"pending", "opted_in", "opted_out"}
ADVOCATE_AVAILABILITIES = {"request_based", "limited", "unavailable"}

ACTIVE_ADVOCATE_REQUEST_STATUSES = {"pending", "matched", "contact_initiated", "accepted"}
TERMINAL_ADVOCATE_REQUEST_STATUSES = {"closed", "declined", "cancelled", "completed"}

LEGACY_ADVOCATE_PROFILES = [
    {
        "key": "general_support",
        "displayName": "General support advocate",
        "publicBio": (
            "Information-only advocate request pathway for general SafeSpeak support "
            "navigation."
        ),
        "languages": ["en"],
        "issueTypes": [
            "general_support",
            "domestic_violence",
            "racial_abuse",
            "migrant_challenges",
            "cyber_scam",
        ],
        "regions": ["AU", "national"],
        "culturalProfiles": [],
        "faithProfiles": [],
        "availability": "request_based",
        "isActive": True,
        "isPublished": False,
        "optInStatus": "pending",
        "vetting": {"status": "pending"},
        "trainingCredentials": [],
    },
    {
        "key": "multilingual_support",
        "displayName": "Multilingual support advocate",
        "publicBio": (
            "Information-only advocate request pathway for multilingual SafeSpeak "
            "support navigation."
        ),
        "languages": ["en", "ar", "es"],
        "issueTypes": ["general_support", "migrant_challenges", "racial_abuse"],
        "regions": ["AU", "national"],
        "culturalProfiles": [],
        "faithProfiles": [],
        "availability": "request_based",
        "isActive": True,
        "isPublished": False,
        "optInStatus": "pending",
        "vetting": {"status": "pending"},
        "trainingCredentials": [],
    },
]

DEFAULT_SUPPORT_SERVICES = [
    {
        "id": "legal-aid",
        "key": "legal-aid",
        "name": "Legal Aid NSW",
        "type": "legal_information",
        "description": (
            "Legal information and referral pathways for people who need help "
            "understanding their options."
        ),
        "cardIcon": "scale",
        "cardOverlayTone": "dark",
        "availabilityLabel": "Available Now",
        "referralTitle": "Warm Referral",
        "referralDescription": (
            "A warm referral ensures the provider has the context they need to help you "
            "immediately without repeating your story. This secure transfer of "
            "information helps build trust and accelerates the support process."
        ),
        "resourceType": "legal",
        "issueTypes": ["workplace_bullying", "racism_discrimination", "general_support"],
        "safetyRiskLevels": ["low", "medium", "high"],
        "ctaLabel": "Contact Legal Aid",
        "phone": "1300 888 529",
        "websiteUrl": "https://www.legalaid.nsw.gov.au/contact-us",
        "jurisdiction": "AU",
        "regions": ["NSW", "national"],
        "languages": ["en"],
        "eligibility": ["legal_help", "racial_abuse", "domestic_violence"],
        "crisis": False,
        "priority": 72,
        "safetyNotes": "Use when the person wants legal information or rights guidance.",
        "eligibilityNotes": "Useful for legal information and referral support.",
        "languageSupportNotes": "Interpreter options depend on the service.",
        "isPublished": True,
        "isActive": True,
        "informationOnly": True,
        "sortOrder": 72,
    },
    {
        "id": "community-support",
        "key": "community-support",
        "name": "Community Support",
        "type": "community",
        "description": (
            "Community-based support options for practical next steps and local service "
            "navigation."
        ),
        "cardIcon": "community",
        "cardOverlayTone": "blue",
        "availabilityLabel": "Available Now",
        "referralTitle": "Warm Referral",
        "referralDescription": (
            "A warm referral ensures the provider has the context they need to help you "
            "immediately without repeating your story. This secure transfer of "
            "information helps build trust and accelerates the support process."
        ),
        "resourceType": "council_support",
        "issueTypes": ["domestic_violence", "racism_discrimination", "general_support"],
        "safetyRiskLevels": ["low", "medium", "high"],
        "ctaLabel": "Find local support",
        "phone": "1800 737 732",
        "websiteUrl": "https://www.1800respect.org.au",
        "jurisdiction": "AU",
        "regions": ["national"],
        "languages": ["en"],
        "eligibility": ["community_support", "racial_abuse", "migrant_support"],
        "crisis": False,
        "priority": 60,
        "safetyNotes": "Useful for local practical support and community referrals.",
        "isPublished": True,
        "isActive": True,
        "informationOnly": True,
        "sortOrder": 60,
    },
    {
        "id": "counselling",
        "key": "counselling",
        "name": "Counselling Support",
        "type": "counselling",
        "description": (
            "Confidential emotional support and counselling pathways for people who need "
            "someone to talk to."
        ),
        "cardIcon": "counselling",
        "cardOverlayTone": "blue",
        "availabilityLabel": "Available Now",
        "referralTitle": "Warm Referral",
        "referralDescription": (
            "A warm referral ensures the provider has the context they need to help you "
            "immediately without repeating your story. This secure transfer of "
            "information helps build trust and accelerates the support process."
        ),
        "resourceType": "mental_health",
        "issueTypes": [
            "domestic_violence",
            "harassment",
            "mental_health_distress",
            "general_support",
        ],
        "safetyRiskLevels": ["low", "medium", "high", "immediate"],
        "ctaLabel": "Call Lifeline",
        "phone": "13 11 14",
        "websiteUrl": "https://www.lifeline.org.au",
        "jurisdiction": "AU",
        "regions": ["national"],
        "languages": ["en"],
        "eligibility": ["mental_health", "domestic_violence", "migrant_support"],
        "crisis": False,
        "priority": 80,
        "languageSupportNotes": "Ask about language support when calling.",
        "isPublished": True,
        "isActive": True,
        "informationOnly": True,
        "sortOrder": 80,
    },
    {
        "id": "health-services",
        "key": "health-services",
        "name": "Healthdirect",
        "type": "health",
        "description": "24/7 health advice from registered nurses and pathways to local care.",
        "cardIcon": "shield",
        "cardOverlayTone": "default",
        "availabilityLabel": "Available Now",
        "referralTitle": "Warm Referral",
        "referralDescription": (
            "A warm referral ensures the provider has the context they need to help you "
            "immediately without repeating your story. This secure transfer of "
            "information helps build trust and accelerates the support process."
        ),
        "resourceType": "government",
        "issueTypes": ["general_support", "mental_health_distress"],
        "safetyRiskLevels": ["low", "medium"],
        "ctaLabel": "Contact Healthdirect",
        "phone": "1800 022 222",
        "websiteUrl": "https://www.healthdirect.gov.au/contact-us",
        "jurisdiction": "AU",
        "regions": ["national"],
        "languages": ["en"],
        "eligibility": ["health", "migrant_support"],
        "crisis": False,
        "priority": 55,
        "isPublished": True,
        "isActive": True,
        "informationOnly": True,
        "sortOrder": 55,
    },
    {
        "id": "elder-support",
        "key": "elder-support",
        "name": "Elder Support",
        "type": "community",
        "description": (
            "Confidential information, advice, and referral options for elder abuse "
            "concerns."
        ),
        "cardIcon": "home",
        "cardOverlayTone": "brown",
        "availabilityLabel": "Available Now",
        "referralTitle": "Warm Referral",
        "referralDescription": (
            "A warm referral ensures the provider has the context they need to help you "
            "immediately without repeating your story. This secure transfer of "
            "information helps build trust and accelerates the support process."
        ),
        "resourceType": "council_support",
        "issueTypes": ["general_support"],
        "safetyRiskLevels": ["low", "medium"],
        "ctaLabel": "View elder support",
        "phone": "1800 353 374",
        "websiteUrl": "https://www.health.gov.au/contacts/elder-abuse-phone-line",
        "jurisdiction": "AU",
        "regions": ["national"],
        "languages": ["en"],
        "eligibility": ["elder_support", "community_support"],
        "crisis": False,
        "priority": 40,
        "isPublished": True,
        "isActive": True,
        "informationOnly": True,
        "sortOrder": 40,
    },
    {
        "id": "crisis-support",
        "key": "crisis-support",
        "name": "1800RESPECT",
        "type": "crisis",
        "description": (
            "National domestic, family and sexual violence counselling, information and "
            "support."
        ),
        "cardIcon": "bell",
        "cardOverlayTone": "red",
        "availabilityLabel": "Available Now",
        "referralTitle": "Warm Referral",
        "referralDescription": (
            "A warm referral ensures the provider has the context they need to help you "
            "immediately without repeating your story. This secure transfer of "
            "information helps build trust and accelerates the support process."
        ),
        "resourceType": "domestic_violence_agency",
        "issueTypes": ["domestic_violence", "harassment"],
        "safetyRiskLevels": ["high", "immediate"],
        "ctaLabel": "Call 1800RESPECT",
        "phone": "1800 737 732",
        "websiteUrl": "https://www.1800respect.org.au",
        "jurisdiction": "AU",
        "regions": ["national"],
        "languages": ["en"],
        "eligibility": ["crisis", "domestic_violence", "safety_plan"],
        "crisis": True,
        "priority": 100,
        "safetyNotes": "Escalate to emergency services when immediate danger is present.",
        "isPublished": True,
        "isActive": True,
        "informationOnly": True,
        "sortOrder": 100,
    },
    {
        "id": "online-safety",
        "key": "online-safety",
        "name": "eSafety Commissioner",
        "type": "online_safety",
        "description": (
            "Online safety reporting pathways for serious online abuse and harmful "
            "online content."
        ),
        "cardIcon": "shield",
        "cardOverlayTone": "purple",
        "availabilityLabel": "Available Now",
        "referralTitle": "Warm Referral",
        "referralDescription": (
            "A warm referral ensures the provider has the context they need to help you "
            "immediately without repeating your story. This secure transfer of "
            "information helps build trust and accelerates the support process."
        ),
        "resourceType": "online_safety",
        "issueTypes": ["online_abuse", "scam_fraud"],
        "safetyRiskLevels": ["low", "medium", "high"],
        "ctaLabel": "Visit eSafety",
        "websiteUrl": "https://www.esafety.gov.au/report",
        "jurisdiction": "AU",
        "regions": ["national"],
        "languages": ["en"],
        "eligibility": ["online_safety", "cyber_scam"],
        "crisis": False,
        "priority": 78,
        "safetyNotes": "Use for cyberbullying, image abuse, or other online abuse pathways.",
        "isPublished": True,
        "isActive": True,
        "informationOnly": True,
        "sortOrder": 78,
    },
]
