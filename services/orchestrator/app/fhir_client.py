from typing import Any

import httpx


class FhirIntegrationError(RuntimeError):
    pass


class FhirIntegrationClient:
    def __init__(
        self,
        base_url: str,
        *,
        timeout_seconds: float = 30.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._client = httpx.AsyncClient(
            base_url=base_url, timeout=timeout_seconds, transport=transport
        )

    async def normalize(self, bundle: dict[str, Any]) -> dict[str, Any]:
        try:
            response = await self._client.post("/v1/fhir/normalize", json=bundle)
        except httpx.HTTPError as exc:
            raise FhirIntegrationError(f"FHIR integration request failed: {exc}") from exc

        if response.status_code not in {200, 422}:
            raise FhirIntegrationError(
                f"FHIR integration returned unexpected status {response.status_code}"
            )
        try:
            result = response.json()
        except ValueError as exc:
            raise FhirIntegrationError("FHIR integration returned invalid JSON") from exc
        if not isinstance(result, dict) or not isinstance(result.get("validation"), dict):
            raise FhirIntegrationError("FHIR integration response violated its contract")
        is_valid = result["validation"].get("isValid")
        canonical_case = result.get("canonicalCase")
        if not isinstance(is_valid, bool):
            raise FhirIntegrationError("FHIR integration response omitted validation.isValid")
        if is_valid and not isinstance(canonical_case, dict):
            raise FhirIntegrationError("Valid FHIR response omitted canonicalCase")
        if not is_valid and canonical_case is not None:
            raise FhirIntegrationError("Invalid FHIR response included canonicalCase")
        if (response.status_code == 200) != is_valid:
            raise FhirIntegrationError("FHIR integration status contradicted validation result")
        return result

    async def health(self) -> None:
        response = await self._client.get("/health")
        response.raise_for_status()

    async def aclose(self) -> None:
        await self._client.aclose()
