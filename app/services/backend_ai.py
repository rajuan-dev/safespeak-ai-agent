# ruff: noqa: E501
import re
from typing import Any, Literal, TypedDict

INFORMATION_ONLY_DISCLAIMER = (
    "This is general information only, not legal advice. For personal legal help, "
    "contact a qualified lawyer, Legal Aid, or a relevant support service."
)

LEGAL_ADVICE_RISK_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"\bsuing is an option\b",
        r"\byou can sue\b",
        r"\byou should sue\b",
        r"\byou must sue\b",
        r"\byou have a case\b",
        r"\bthis is definitely illegal\b",
        r"\bthat is definitely illegal\b",
        r"\bthey broke the law\b",
        r"\byou will win\b",
        r"\byou are entitled to compensation\b",
    )
]

CLINICAL_ADVICE_RISK_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"\byou have (ptsd|depression|anxiety|trauma)\b",
        r"\bi diagnose\b",
        r"\bclinical advice\b",
        r"\bmedical advice\b",
        r"\btake (this )?medication\b",
        r"\bstop taking (your )?medication\b",
        r"\btherapy plan\b",
    )
]

CRISIS_RISK_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"\bi am in danger\b",
        r"\bi'?m in danger\b",
        r"\bimmediate danger\b",
        r"\bi am unsafe\b",
        r"\bi'?m unsafe\b",
        r"\bunsafe right now\b",
        r"\bi need help now\b",
        r"\bpartner is threatening me\b",
        r"\bmy partner is threatening me\b",
        r"\bdomestic violence\b",
        r"\bthreat to life\b",
        r"\bviolence now\b",
    )
]

SOURCE_GROUNDED_TOPIC_RE = re.compile(
    r"\b(?:acts?|regulations?|laws?|legal|rights|sections?|citations?|cite|sources?|"
    r"reports?|reporting|complaints?|complain|agenc(?:y|ies)|ombudsman|commission|"
    r"tribunal|court|police|privacy|anti-discrimination|discrimination|fair work|"
    r"esafety|oaic|ahrc|scamwatch|legal aid|legislation)\b",
    re.IGNORECASE,
)
HIGH_IMPACT_LEGAL_RE = re.compile(
    r"\b(?:sue|lawsuit|court|tribunal|police report|report to police|protective order|"
    r"avo|ivo|dvo|visa|immigration|deport|deported|custody|child protection|evidence|"
    r"recording|surveillance|litigation)\b",
    re.IGNORECASE,
)
LEGAL_OR_RIGHTS_TOPIC_RE = re.compile(
    r"\b(?:legal|illegal|law|rights|case|legislation)\b", re.IGNORECASE
)
REPORTING_PATHWAY_QUESTION_RE = re.compile(
    r"\b(?:where can i report|reportcyber|scamwatch|esafety|fair work|"
    r"anti discrimination|anti-discrimination|police report|what are my rights)\b",
    re.IGNORECASE,
)
AGENCY_QUESTION_RE = re.compile(
    r"\b(?:which agency|what pathway|who do i report to|what are my reporting options|"
    r"reporting options)\b",
    re.IGNORECASE,
)
LEGAL_ASSISTANCE_SERVICES_RE = re.compile(
    r"\b(?:what|which|where|who)\b.*\b(?:legal assistance|legal aid|legal service|"
    r"legal services|lawyer|lawyers|community legal centre|community legal centres|"
    r"wdvcas|family violence prevention legal services)\b",
    re.IGNORECASE,
)
FACTUAL_SOURCE_RE = re.compile(
    r"\b(?:according to|aihw|uploaded\s+(?:document|report|source)|(?:this|the)\s+"
    r"(?:document|report|source|act|legislation)|cite|citation|page\s+number|"
    r"section\s+[0-9a-z])\b",
    re.IGNORECASE,
)
FACTUAL_REQUEST_RE = re.compile(
    r"\b(?:what|which|when|where|who|how many|how much|percentage|percent|rate|"
    r"number|date|define|definition|called|state|territor|compare|difference|"
    r"does|did|is|are|was|were)\b",
    re.IGNORECASE,
)

AU_WRONG_EMERGENCY_PATTERNS = [re.compile(r"\b911\b"), re.compile(r"\b999\b"), re.compile(r"\b112\b")]
FALSE_ACTION_CLAIM_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"\bi uploaded\b",
        r"\bwe uploaded\b",
        r"\bsafespeak uploaded\b",
        r"\bi shared this\b",
        r"\bi sent it to an agency\b",
        r"\bi sent this to police\b",
        r"\bi contacted an agency\b",
        r"\bi contacted police\b",
        r"\bi analy[sz]ed the file\b",
        r"\byour evidence has been saved\b",
        r"\byour evidence has been synced\b",
        r"\byour (?:photo|photos|file|files|evidence) (?:has|have) been "
        r"(?:uploaded|saved|shared|sent|synced)\b",
        r"\b(?:this|it|the file|the evidence) (?:has|have) been "
        r"(?:uploaded|saved|sent|shared|synced)\b",
    )
]
ROLE_VIOLATION_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"\bi am your lawyer\b",
        r"\bi am your counsellor\b",
        r"\bi diagnosed\b",
        r"\bi can represent you\b",
        r"\bi will manage your case\b",
        r"\bi contacted police\b",
    )
]
SAFETY_PROMISE_PATTERNS = [
    re.compile(r"\byou are safe now\b", re.IGNORECASE),
    re.compile(r"\beverything will be okay\b", re.IGNORECASE),
]
EVIDENCE_LEGAL_STRATEGY_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"\bhard to dispute\b",
        r"\bstrong evidence\b",
        r"\bprove your case\b",
        r"\bbuild your case\b",
        r"\buse this against them\b",
        r"\bthis proves\b",
    )
]

Intent = Literal[
    "safety_crisis",
    "physical_harm",
    "incident_disclosure",
    "evidence_upload",
    "encoding_error",
    "ai_analysis_question",
    "legal_boundary_specific_case",
    "legal_general_information",
    "rag_pathway_question",
    "scam_check",
    "language_or_translation",
    "meta_feedback",
    "general_conversation",
    "format_preference_question",
    "format_preference_set",
    "unknown",
]


class IntentClassification(TypedDict):
    intent: Intent
    confidence: Literal["high", "medium", "low"]
    matchedSignals: list[str]
    classifierSource: Literal["rule", "model", "hybrid"]


class TurnPolicy(TypedDict):
    responseStrategy: str
    ragRequired: bool
    ragReason: str
    groundedAnswerRequired: bool
    questionAllowed: bool
    maxQuestions: int
    disclaimerRequired: bool
    sourcesVisible: bool
    pathwayAllowed: bool
    timelineCollectionAllowed: bool
    humanReviewRequired: bool
    humanReviewRecommended: bool
    humanReviewReasons: list[str]
    principleOrder: list[str]


def collapse_whitespace(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def normalize_message(value: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9\s?]", " ", collapse_whitespace(value).lower())).strip()


def _collect_signals(normalized: str, rules: list[tuple[str, str]]) -> list[str]:
    return [signal for signal, pattern in rules if re.search(pattern, normalized)]


def classify_intent(message: str) -> IntentClassification:
    normalized = normalize_message(message)
    if not normalized:
        return {"intent": "unknown", "confidence": "low", "matchedSignals": [], "classifierSource": "rule"}

    if re.search(r"\b(are you (answering|using)|why are you using|do you always answer with|every time)\b", normalized) and re.search(r"\b(bullet point|bullet points|bullets)\b", normalized):
        return {"intent": "format_preference_question", "confidence": "high", "matchedSignals": ["format_preference_question"], "classifierSource": "rule"}

    buckets: list[tuple[Intent, Literal["high", "medium"], list[tuple[str, str]]]] = [
        ("safety_crisis", "high", [
            ("immediate_danger_phrase", r"\b(right now|outside my house|still here|still outside|coming back|following me)\b"),
            ("weapon_or_kill_threat", r"\b(weapon|knife|gun|kill me|kill us|threatening me right now)\b"),
            ("unsafe_phrase", r"\b(i am in danger|im in danger|unsafe right now|emergency)\b"),
        ]),
        ("physical_harm", "high", [
            ("physical_harm_phrase", r"\b(someone hit me|some one hit me|hit me|punched me|slapped me|kicked me|assaulted me|attacked me|hurt me)\b"),
            ("incident_with_hit", r"\b(i was|i am|someone|some one)\b.*\b(hit|punched|slapped|kicked|assaulted|attacked)\b"),
            ("physical_contact_hijab", r"\b(pulled|grabbed|snatched|touched)\b.*\b(hijab|headscarf|veil)\b"),
        ]),
        ("ai_analysis_question", "high", [
            ("ai_analysis_question", r"\b(ai|artificial intelligence)\b.*\b(analy[sz]e|process|read|review|scan|check)\b"),
            ("analysis_after_upload", r"\b(will ai analy[sz]e|if i upload.*will ai|will safespeak analy[sz]e)\b"),
        ]),
        ("evidence_upload", "high", [
            ("evidence_upload_terms", r"\b(upload|attach|share|add)\b.*\b(screenshot|screenshots|photo|photos|image|images|file|files|document|documents|evidence|proof)\b"),
            ("evidence_question", r"\b(can i upload|can i attach|i have screenshots|i have proof|i have photos|i have photo)\b"),
            ("documentation_request", r"\b(help me document|can you help me document|how should i document it|document it)\b"),
        ]),
        ("legal_boundary_specific_case", "high", [
            ("legal_boundary_question", r"\b(is this illegal|can i sue|do i have a case|did they break the law|is that against the law|can police arrest them|is this criminal)\b"),
            ("case_specific_legal_question", r"\b(what are my legal options|what are my rights here|can i take legal action)\b"),
        ]),
        ("legal_general_information", "high", [
            ("general_legal_explainer", r"\b(explain|tell me about|summary of|briefly explain|what does .* mean|give me a summary of)\b.*\b(criminal law|australian law|discrimination law|legal pathways|law generally)\b"),
            ("topic_only_legal_explainer", r"\b(about )?(criminal law|australian criminal law|discrimination law|legal pathways)\b"),
            ("named_legislation_lookup", r"\b(what|which|how|why|does|did|according to|under|summary|explain)\b.*\b(act|regulation|code|charter|constitution|policy)\b.*\b\d{4}\b"),
            ("section_lookup_question", r"\b(what section|which section|what does this act say|what does the act say|what did this act change|what did the act change)\b"),
        ]),
    ]
    for intent, confidence, rules in buckets:
        signals = _collect_signals(normalized, rules)
        if signals:
            if intent == "legal_general_information" and len(normalized.split()) <= 4:
                confidence = "medium"
            return {"intent": intent, "confidence": confidence, "matchedSignals": signals, "classifierSource": "rule"}

    if REPORTING_PATHWAY_QUESTION_RE.search(normalized) or AGENCY_QUESTION_RE.search(normalized) or LEGAL_ASSISTANCE_SERVICES_RE.search(normalized):
        return {"intent": "rag_pathway_question", "confidence": "medium", "matchedSignals": ["rag_pathway_question"], "classifierSource": "rule"}

    scam_signals = _collect_signals(normalized, [
        ("scam_term", r"\b(scam|fraud|phishing|fake link|otp|reportcyber|scamwatch)\b"),
        ("identity_or_bank_risk", r"\b(bank details|identity theft|passport|credit card|account hacked)\b"),
        ("scam_warning_signs_request", r"\b(warning signs|red flags)\b"),
    ])
    if scam_signals:
        return {"intent": "scam_check", "confidence": "high" if len(scam_signals) > 1 else "medium", "matchedSignals": scam_signals, "classifierSource": "rule"}

    incident_signals = _collect_signals(normalized, [
        ("incident_disclosure_term", r"\b(happened|harassed|threatened|abused|followed me|touched me|they did this to me)\b"),
        ("distress_context", r"\b(scared|upset|someone followed me|someone touched me)\b"),
        ("workplace_mocking_or_belonging", r"\b(boss|manager|supervisor|coworker|co worker|colleague|work)\b.*\b(mock|mocking|laugh|accent|belong|do not belong|dont belong|humiliat|put me down)\b"),
        ("privacy_or_personal_info_disclosure", r"\b(shared|emailed|sent|leaked|posted|showed|told)\b.*\b(health info|health information|private information|private info|personal details|my details|messages|photos)\b"),
    ])
    if incident_signals:
        return {"intent": "incident_disclosure", "confidence": "medium", "matchedSignals": incident_signals, "classifierSource": "rule"}

    if re.search(r"\b(can you speak|speak in|translate|bangla|bengali|arabic|hindi|spanish)\b", normalized):
        return {"intent": "language_or_translation", "confidence": "high", "matchedSignals": ["language_request"], "classifierSource": "rule"}
    if re.search(r"\b(you sound scripted|it sounds scripted|too scripted|why are you repeating|too repetitive|why do you sound|why are you so generic|your answer is wrong|be smart like chatgpt|respond like chatgpt|make it more natural|don t be static)\b", normalized):
        return {"intent": "meta_feedback", "confidence": "high", "matchedSignals": ["meta_feedback"], "classifierSource": "rule"}
    if re.search(r"^(hi|hello|hey|good morning|good evening)\b", normalized) or re.search(r"\b(what can you do|i need help|can you help me|i need support|i want some help|can i talk to you|i want to talk|can we talk)\b", normalized):
        return {"intent": "general_conversation", "confidence": "high", "matchedSignals": ["general_conversation"], "classifierSource": "rule"}
    if re.search(r"\b(please answer in paragraphs|answer in paragraphs|please use paragraphs|use paragraphs|not bullet points|don t use bullets|do not use bullets|stop using bullet points|without bullet points|not bullets|please use bullet points|use bullet points|answer in bullet points|give me bullet points|please use bullets|mix|mixed format|some bullets|both paragraphs and bullets)\b", normalized):
        return {"intent": "format_preference_set", "confidence": "high", "matchedSignals": ["format_preference_set"], "classifierSource": "rule"}
    if len(normalized.split()) <= 2:
        return {"intent": "general_conversation", "confidence": "low", "matchedSignals": ["short_general_turn"], "classifierSource": "rule"}
    return {"intent": "unknown", "confidence": "low", "matchedSignals": [], "classifierSource": "rule"}


def requires_grounded_factual_answer(message: str) -> bool:
    normalized = collapse_whitespace(message)
    return bool(FACTUAL_SOURCE_RE.search(normalized) and (FACTUAL_REQUEST_RE.search(normalized) or "?" in normalized))


def response_mode_for_intent(intent: str) -> str:
    return {
        "safety_crisis": "emergency_safety",
        "evidence_upload": "evidence_upload_intent",
        "meta_feedback": "meta_feedback",
        "legal_boundary_specific_case": "legal_lookup",
        "legal_general_information": "legal_lookup",
        "rag_pathway_question": "legal_lookup",
        "scam_check": "scamshield_style",
        "physical_harm": "support_victim_style",
        "incident_disclosure": "support_victim_style",
    }.get(intent, "clarification_needed" if intent == "unknown" else "support_victim_style")


def build_turn_policy(intent: str, message: str, response_mode: str) -> TurnPolicy:
    normalized = collapse_whitespace(message)
    rag_required = False
    rag_reason = "not_required"
    if normalized:
        if response_mode == "legal_lookup":
            rag_required = True
            rag_reason = "legal_lookup"
        elif intent in {"legal_boundary_specific_case", "rag_pathway_question"}:
            rag_required = True
            rag_reason = "required_intent"
        elif requires_grounded_factual_answer(normalized) or SOURCE_GROUNDED_TOPIC_RE.search(normalized):
            rag_required = True
            rag_reason = "source_grounded_request"

    human_review_reasons: list[str] = []
    if response_mode == "legal_lookup" or intent == "legal_boundary_specific_case" or HIGH_IMPACT_LEGAL_RE.search(normalized):
        human_review_reasons.append("may_influence_legal_or_reporting_decision")

    grounded = response_mode == "legal_lookup" or rag_required and rag_reason in {"source_grounded_request", "required_intent"}
    response_strategy = "support_only"
    question_allowed = True
    max_questions = 1
    disclaimer_required = False
    sources_visible = False
    pathway_allowed = True
    timeline_collection_allowed = False

    if response_mode == "triage_handoff":
        response_strategy, question_allowed, max_questions = "triage_handoff", False, 0
    elif response_mode == "emergency_safety":
        response_strategy, question_allowed, max_questions = "safety_override", False, 0
    elif response_mode == "meta_feedback":
        response_strategy, pathway_allowed = "meta_feedback", False
    elif response_mode == "evidence_upload_intent":
        response_strategy, disclaimer_required, timeline_collection_allowed = "evidence_guidance", True, True
    elif response_mode == "legal_lookup":
        response_strategy, disclaimer_required, sources_visible, timeline_collection_allowed = "grounded_legal_information", True, True, True
    elif grounded:
        response_strategy, disclaimer_required, sources_visible = "pathway_guidance", True, True
    elif response_mode == "clarification_needed":
        response_strategy, pathway_allowed = "support_only", False

    return {
        "responseStrategy": response_strategy,
        "ragRequired": rag_required,
        "ragReason": rag_reason,
        "groundedAnswerRequired": grounded,
        "questionAllowed": question_allowed,
        "maxQuestions": max_questions,
        "disclaimerRequired": disclaimer_required,
        "sourcesVisible": sources_visible,
        "pathwayAllowed": pathway_allowed,
        "timelineCollectionAllowed": timeline_collection_allowed,
        "humanReviewRequired": response_mode == "legal_lookup",
        "humanReviewRecommended": bool(human_review_reasons),
        "humanReviewReasons": human_review_reasons,
        "principleOrder": [
            "human_first",
            "triage_before_data_collection",
            "minimum_necessary_information",
            "understand_not_decide",
            "pathways_over_laws",
            "authoritative_rag_only",
        ],
    }


def detect_progressive_stage(message: str) -> str:
    if re.search(r"\b(report(ing)? options?|who do i report to|where can i report|which agency|police report)\b", message, re.IGNORECASE):
        return "user_requests_reporting"
    if re.search(r"\b(how can i|how do i|help me|can you help me|please help me)\b.*\b(document|documentation|organi[sz]e|timeline|evidence|photos?|screenshots?|record)\b|\b(document it|organise it|organize it|help me document)\b", message, re.IGNORECASE):
        return "user_requests_documentation"
    if re.search(r"\b(illegal|legal|law|sue|rights|case)\b", message, re.IGNORECASE):
        return "user_requests_legal_info"
    if re.search(r"\b(options?|what can i do|next steps?|what now)\b", message, re.IGNORECASE):
        return "user_requests_options"
    if re.search(r"\b(build|draft|prepare)\b.*\b(report|timeline|statement)\b", message, re.IGNORECASE):
        return "report_building_mode"
    return "first_response"


def build_response_plan(intent: str, message: str, turn_policy: TurnPolicy) -> dict[str, Any]:
    stage = detect_progressive_stage(message)
    base: dict[str, Any] = {
        "maxDepth": "shallow",
        "maxQuestions": 1,
        "questionAllowed": True,
        "preferredFormat": "short_paragraphs",
        "emergencyPriority": False,
        "progressiveDisclosureStage": stage,
    }
    plans: dict[str, dict[str, Any]] = {
        "general_conversation": {
            "primaryGoal": "greet_or_capability",
            "allowedContent": ["one warm direct sentence", "one simple invitation to share"],
            "deferredContent": ["capability lists", "multiple questions", "legal detail"],
        },
        "meta_feedback": {
            "primaryGoal": "answer_feedback",
            "allowedContent": ["brief acknowledgement", "direct answer to the feedback"],
            "deferredContent": ["incident pathways", "legal detail", "service lists"],
        },
        "safety_crisis": {
            "primaryGoal": "crisis_response",
            "allowedContent": ["immediate safety direction", "000 if urgent risk in Australia", "one brief safety question"],
            "deferredContent": ["documentation checklist", "reporting detail", "legal detail"],
            "emergencyPriority": True,
        },
        "evidence_upload": {
            "primaryGoal": "evidence_privacy_guidance" if stage == "user_requests_documentation" else "general_guidance",
            "allowedContent": ["privacy and consent reminder", "no false upload/share claim"],
            "deferredContent": ["legal strategy", "police or agency steps unless asked"],
        },
        "legal_boundary_specific_case": {
            "primaryGoal": "legal_boundary",
            "allowedContent": ["information only", "cannot decide legality or whether the user can sue", "one minimal state or context question"],
            "deferredContent": ["detailed legal explanation unless asked", "pathway list unless sources are available"],
        },
        "legal_general_information": {
            "primaryGoal": "general_education",
            "allowedContent": ["general explanation", "information-only framing"],
            "deferredContent": ["case-specific legal conclusion", "service lists unless asked"],
            "maxDepth": "medium",
            "preferredFormat": "concise_sections",
        },
        "rag_pathway_question": {
            "primaryGoal": "general_guidance",
            "allowedContent": ["reporting or pathway options because the user asked"],
            "deferredContent": ["case-specific legal conclusion"],
            "maxDepth": "medium",
            "preferredFormat": "bullets_or_steps",
        },
        "scam_check": {
            "primaryGoal": "scam_warning_signs",
            "allowedContent": ["red flags", "safe verification steps"],
            "deferredContent": ["reporting pathways unless asked", "legal detail"],
            "maxDepth": "medium",
            "preferredFormat": "bullets",
        },
    }
    if intent in {"physical_harm", "incident_disclosure", "unknown"}:
        plans[intent] = {
            "primaryGoal": "emotional_support_and_user_control",
            "allowedContent": ["two or three short sentences of grounded emotional support", "one optional choice-based question"],
            "deferredContent": ["documentation checklist", "reporting options", "legal classification", "service list"],
        }
    plan = {**base, **plans.get(intent, {"primaryGoal": "general_guidance", "allowedContent": ["direct answer to the user's immediate ask"], "deferredContent": ["extra pathways not yet requested"]})}
    plan.update(
        {
            "maxQuestions": min(int(plan["maxQuestions"]), turn_policy["maxQuestions"]),
            "questionAllowed": turn_policy["questionAllowed"],
            "responseStrategy": turn_policy["responseStrategy"],
            "groundedAnswerRequired": turn_policy["groundedAnswerRequired"],
            "disclaimerRequired": turn_policy["disclaimerRequired"],
            "sourcesVisible": turn_policy["sourcesVisible"],
            "pathwayAllowed": turn_policy["pathwayAllowed"],
            "timelineCollectionAllowed": turn_policy["timelineCollectionAllowed"],
            "humanReviewRequired": turn_policy["humanReviewRequired"],
        }
    )
    return plan


def split_guardrail_violations(violations: list[str]) -> dict[str, list[str]]:
    hard = {"wrong_au_emergency_number", "legal_conclusion", "false_action_claim", "role_violation", "safety_promise"}
    return {
        "hard": [violation for violation in violations if violation in hard],
        "soft": [violation for violation in violations if violation not in hard],
    }


def validate_response(
    *,
    text: str,
    intent: str,
    latest_user_message: str,
    response_plan: dict[str, Any],
) -> dict[str, Any]:
    violations: set[str] = set()
    if any(pattern.search(text) for pattern in AU_WRONG_EMERGENCY_PATTERNS):
        violations.add("wrong_au_emergency_number")
    has_boundary = bool(re.search(r"\b(?:cannot|can't|can’t)\s+(?:decide|say|tell|determine)\b|\binformation only\b|\bnot legal advice\b", text, re.IGNORECASE))
    if any(pattern.search(text) for pattern in LEGAL_ADVICE_RISK_PATTERNS) and not has_boundary:
        violations.add("legal_conclusion")
    if re.search(r"\byou can sue\b", text, re.IGNORECASE) and not re.search(r"\bwhether you can sue\b", text, re.IGNORECASE):
        violations.add("legal_conclusion")
    if intent == "legal_boundary_specific_case" and not re.search(r"\b(not legal advice|information only)\b", text, re.IGNORECASE):
        violations.add("missing_legal_boundary_disclaimer")
    if any(pattern.search(text) for pattern in FALSE_ACTION_CLAIM_PATTERNS):
        violations.add("false_action_claim")
    if any(pattern.search(text) for pattern in ROLE_VIOLATION_PATTERNS):
        violations.add("role_violation")
    if any(pattern.search(text) for pattern in SAFETY_PROMISE_PATTERNS):
        violations.add("safety_promise")
    if any(pattern.search(text) for pattern in EVIDENCE_LEGAL_STRATEGY_PATTERNS):
        violations.add("evidence_legal_strategy")
    if text.count("?") > int(response_plan.get("maxQuestions", 1)):
        violations.add("too_many_questions")
    if response_plan.get("disclaimerRequired") and (
        LEGAL_OR_RIGHTS_TOPIC_RE.search(text) or re.search(r"\b(report(?:ing)?|pathway|agency|police|tribunal|court)\b", text, re.IGNORECASE)
    ) and not re.search(r"\b(not legal advice|information only)\b", text, re.IGNORECASE):
        violations.add("missing_legal_boundary_disclaimer")
    if response_plan.get("progressiveDisclosureStage") == "first_response":
        if not re.search(r"\b(report|reporting|police|agency|where can i report|options)\b", latest_user_message, re.IGNORECASE) and len(re.findall(r"\bpolice\b|\breport(?:ing)?\b|\bagency\b", text, re.IGNORECASE)) >= 2:
            violations.add("premature_reporting")
        if response_plan.get("pathwayAllowed") is False and re.search(r"\b(police|report(?:ing)?|agency|pathway|options?)\b", text, re.IGNORECASE):
            violations.add("too_many_pathways")
    return {"passed": not violations, "violations": sorted(violations)}
