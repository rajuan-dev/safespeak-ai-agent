PLATFORM_HEALTH_CHECKS = [
    {
        "id": "api",
        "label": "API readiness",
        "category": "core",
        "status": "ready",
        "owner": "backend",
        "metric": "Routers mounted",
        "summary": "FastAPI admin surfaces are registered and responding.",
        "details": ["Foundation, auth, content, analytics, and admin routers are active."],
    },
    {
        "id": "privacy",
        "label": "Privacy controls",
        "category": "security",
        "status": "ready",
        "owner": "backend",
        "metric": "Audit + consent paths",
        "summary": "Audit logging and privacy workflows remain available in FastAPI.",
        "details": ["Sensitive actions continue to create audit entries.", "Consent and privacy modules are routed through FastAPI."],
    },
]
