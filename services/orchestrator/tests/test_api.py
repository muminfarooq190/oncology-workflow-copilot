from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def synthetic_bundle() -> dict:
    return {
        "resourceType": "Bundle",
        "meta": {
            "tag": [
                {
                    "system": "https://oncology-copilot.dev/tags",
                    "code": "synthetic",
                }
            ]
        },
        "type": "collection",
        "entry": [],
    }


def test_liveness() -> None:
    response = client.get("/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "orchestrator", "version": "0.1.0"}


def test_accepts_explicitly_synthetic_bundle_idempotently() -> None:
    request = {"fhirBundle": synthetic_bundle()}
    headers = {"Idempotency-Key": "case-nsclc-001"}

    first = client.post("/v1/workflows", json=request, headers=headers)
    second = client.post("/v1/workflows", json=request, headers=headers)

    assert first.status_code == 202
    assert first.json()["workflowId"] == second.json()["workflowId"]
    assert first.json()["status"] == "received"
    assert first.headers["location"].endswith(first.json()["workflowId"])


def test_rejects_non_bundle_input() -> None:
    response = client.post(
        "/v1/workflows",
        json={"fhirBundle": {"resourceType": "Patient"}},
        headers={"Idempotency-Key": "invalid-patient"},
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "fhirBundle.resourceType must be Bundle"


def test_rejects_bundle_without_synthetic_marker() -> None:
    response = client.post(
        "/v1/workflows",
        json={"fhirBundle": {"resourceType": "Bundle", "entry": []}},
        headers={"Idempotency-Key": "untagged-bundle"},
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "Only bundles explicitly tagged as synthetic are accepted"

