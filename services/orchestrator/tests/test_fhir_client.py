import httpx
import pytest

from app.fhir_client import FhirIntegrationClient, FhirIntegrationError


def _transport(payload: dict, status_code: int) -> httpx.MockTransport:
    return httpx.MockTransport(lambda _: httpx.Response(status_code, json=payload))


@pytest.mark.asyncio
async def test_accepts_valid_normalization_contract() -> None:
    expected = {
        "validation": {"isValid": True, "issues": []},
        "canonicalCase": {"schemaVersion": "1.0.0"},
    }
    client = FhirIntegrationClient(
        "http://fhir.test", transport=_transport(expected, status_code=200)
    )

    try:
        assert await client.normalize({"resourceType": "Bundle"}) == expected
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_rejects_status_body_contradiction() -> None:
    client = FhirIntegrationClient(
        "http://fhir.test",
        transport=_transport(
            {"validation": {"isValid": True}, "canonicalCase": {"caseId": "case-1"}},
            status_code=422,
        ),
    )

    try:
        with pytest.raises(FhirIntegrationError, match="status contradicted"):
            await client.normalize({"resourceType": "Bundle"})
    finally:
        await client.aclose()
