import asyncio
from collections.abc import Mapping
from uuid import UUID

from redis.asyncio import Redis
from redis.exceptions import ResponseError

from app.config import Settings, get_settings
from app.db import dispose_engine, get_session_factory
from app.fhir_client import FhirIntegrationClient
from app.redis_client import close_redis, get_redis
from app.repository import WorkflowService


class WorkflowWorker:
    def __init__(
        self,
        redis: Redis,
        service: WorkflowService,
        fhir: FhirIntegrationClient,
        settings: Settings,
    ) -> None:
        self._redis = redis
        self._service = service
        self._fhir = fhir
        self._settings = settings

    async def ensure_consumer_group(self) -> None:
        try:
            await self._redis.xgroup_create(
                self._settings.workflow_stream,
                self._settings.workflow_consumer_group,
                id="0",
                mkstream=True,
            )
        except ResponseError as exc:
            if "BUSYGROUP" not in str(exc):
                raise

    async def process_message(self, message_id: str, fields: Mapping[str, str]) -> None:
        workflow_id = UUID(fields["workflowId"])
        outbox_id = UUID(fields["outboxId"])
        trace_id = fields["traceId"]
        workflow = await self._service.claim_normalization(
            workflow_id, outbox_id=outbox_id, trace_id=trace_id
        )
        if workflow is None:
            await self._ack(message_id)
            return

        try:
            result = await self._fhir.normalize(workflow.fhir_bundle)
            await self._service.complete_normalization(
                workflow_id,
                validation_result=result["validation"],
                canonical_case=result.get("canonicalCase"),
                trace_id=trace_id,
            )
        except Exception as exc:
            await self._service.fail_normalization(
                workflow_id,
                error_code=type(exc).__name__,
                error_message=str(exc),
                trace_id=trace_id,
            )
        await self._ack(message_id)

    async def read_once(self, *, block_milliseconds: int | None = None) -> int:
        messages = await self._redis.xreadgroup(
            self._settings.workflow_consumer_group,
            self._settings.workflow_consumer_name,
            {self._settings.workflow_stream: ">"},
            count=10,
            block=(
                self._settings.worker_poll_milliseconds
                if block_milliseconds is None
                else block_milliseconds
            ),
        )
        return await self._process_stream_messages(messages)

    async def reclaim_once(self) -> int:
        result = await self._redis.xautoclaim(
            self._settings.workflow_stream,
            self._settings.workflow_consumer_group,
            self._settings.workflow_consumer_name,
            min_idle_time=self._settings.worker_claim_idle_milliseconds,
            start_id="0-0",
            count=10,
        )
        messages = result[1]
        processed = 0
        for message_id, fields in messages:
            await self.process_message(message_id, fields)
            processed += 1
        return processed

    async def run_forever(self) -> None:
        await self.ensure_consumer_group()
        while True:
            await self.reclaim_once()
            await self.read_once()

    async def _process_stream_messages(self, streams: list) -> int:
        processed = 0
        for _, messages in streams:
            for message_id, fields in messages:
                await self.process_message(message_id, fields)
                processed += 1
        return processed

    async def _ack(self, message_id: str) -> None:
        await self._redis.xack(
            self._settings.workflow_stream,
            self._settings.workflow_consumer_group,
            message_id,
        )


async def _main() -> None:
    settings = get_settings()
    fhir = FhirIntegrationClient(settings.fhir_integration_url)
    worker = WorkflowWorker(
        get_redis(), WorkflowService(get_session_factory(), settings), fhir, settings
    )
    try:
        await worker.run_forever()
    finally:
        await fhir.aclose()
        await close_redis()
        await dispose_engine()


if __name__ == "__main__":
    asyncio.run(_main())
