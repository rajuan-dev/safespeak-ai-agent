# Legal Golden Corpus

`synthetic-manifest.json` is a deterministic CI smoke test. It does not certify legal
correctness.

`candidate-manifest.json` contains machine-checked official PDFs that still require
human legal review before changing `fixtureType` from `candidate_real` to
`reviewed_real`.

Production certification requires a separate manifest containing at least eight
`reviewed_real` Australian legislation PDFs, including Commonwealth and state
legislation, at least one table-bearing document, and at least one schedule-bearing
document. Each fixture must contain at least five manually reviewed
question-to-citation expectations.

Store PDFs outside Git when licensing or size requires it. Set `pdfPath` relative to
the manifest and pin every document with `sha256`. Never silently replace a reviewed
PDF with a newer consolidation: add a new fixture/version and repeat legal review.

Download and pin an official PDF:

```powershell
python scripts/pin_legal_pdf.py "OFFICIAL_PDF_URL" `
  legal-golden/reviewed/example-act.pdf
```

Run:

```powershell
python scripts/generate_synthetic_golden.py
python -m app.evaluation.golden legal-golden/synthetic-manifest.json
python -m app.evaluation.golden legal-golden/candidate-manifest.json
python -m app.evaluation.golden legal-golden/production-manifest.json --require-production
```
