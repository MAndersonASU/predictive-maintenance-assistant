# Professional Demonstration Interface

## Purpose and scope

The root path (`/`) presents a professional local interface over the already-implemented FastAPI contracts. It connects the frozen prediction model, governed retrieval, citation-grounded answers, evidence inspection, readiness, counters, and bounded local review evidence without introducing a second business-logic path.

This is a **bounded local demonstration release candidate**, not a public service. It does not refit or retune the Isolation Forest, change the frozen 48-feature schema or threshold, rebuild the 354-chunk corpus, rebuild the hybrid index, alter grounding behavior, or rerun either held-out evaluator.

## Demonstration workspaces

### Knowledge and evidence

The knowledge workspace sends the same question to `POST /api/v1/retrieve` and `POST /api/v1/answer`. It displays the governed answer status, reason code, intent, request ID, citations, source classification, and locator metadata. If exact-equipment evidence is unavailable, the existing refusal boundary remains visible rather than being replaced by generic guidance.

### Prediction

The prediction workspace loads `GET /api/v1/prediction/schema`, displays the frozen feature count and threshold, and requires one JSON object with exactly the frozen feature names before calling `POST /api/v1/predict`. A zero-valued template is available only to inspect the request contract. It is clearly labeled synthetic and is not presented as operational evidence.

The result reports the unusualness score, frozen threshold, alarm decision, interpretation, and request ID. The interface states that unusualness is not a failure probability and that a threshold alarm does not establish a verified failure state.

### Operations

The operations workspace reads `/health/ready`, `/api/v1/metrics`, and `/api/v1/evaluations`. It shows local readiness, interaction counts, and local review counts. These are bounded demonstration records and do not change governed ML or RAG evaluation evidence.

## Security and privacy controls

- The interface is self-contained: no CDN, remote font, analytics script, external inference endpoint, or browser storage.
- A content-security policy limits scripts, styles, images, and connections to the local application origin.
- Fixed asset names are allowlisted; arbitrary paths are not served.
- Responses disable caching, MIME sniffing, framing, and referrer transmission.
- API validation, sanitized errors, loopback enforcement, request IDs, redacted persistence, and bounded retention remain unchanged.
- Authentication remains disabled because the application is not authorized for public network exposure.

## Run and verify

With the governed model, feature, corpus, and retrieval-index artifacts present at their configured paths:

```powershell
$env:PYTHONPATH = "src"
python -m predictive_maintenance.application.api
```

Open `http://127.0.0.1:8000/`. OpenAPI documentation remains available at `http://127.0.0.1:8000/docs`.

Focused verification:

```powershell
python -m pytest -q tests/test_application_demo.py tests/test_application_api.py
```

The tests verify local asset completeness, absence of remote dependencies, security headers, fixed asset routing, governed API-path use, absence of browser persistence, and the complete UI-to-schema/prediction/retrieval/answer path using controlled application dependencies.
