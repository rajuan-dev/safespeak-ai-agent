import json
from pathlib import Path

import fitz

from app.evaluation.golden import evaluate_manifest


def test_synthetic_golden_passes_but_does_not_claim_production_ready(tmp_path: Path):
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 60), "Example Act 2026", fontsize=18, fontname="hebo")
    page.insert_text((72, 90), "As at 21 June 2026", fontsize=10)
    page.insert_text((72, 125), "1 Short title", fontsize=14, fontname="hebo")
    page.insert_text((72, 150), "This Act is the Example Act 2026.", fontsize=10)
    pdf_path = tmp_path / "example.pdf"
    document.save(pdf_path)
    document.close()
    manifest = {
        "fixtures": [
            {
                "id": "synthetic",
                "fixtureType": "synthetic",
                "pdfPath": "example.pdf",
                "title": "Example Act 2026",
                "jurisdiction": "Cth",
                "sourceUrl": "https://example.invalid/act",
                "expectations": {
                    "minimumPages": 1,
                    "minimumSections": 1,
                    "requiredText": ["Short title"],
                    "expectedSections": [{"sectionRef": "1", "page": 1}],
                    "versionDate": "2026-06-21",
                },
                "questions": [
                    {
                        "question": "What is the short title in section 1?",
                        "expectedSectionRef": "1",
                        "expectedRank": 1,
                    }
                ],
            }
        ]
    }
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    report = evaluate_manifest(manifest_path)

    assert report.passed
    assert not report.productionReady
    assert report.realFixtureCount == 0

