import asyncio
from datetime import UTC, datetime

from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import Settings, get_settings
from app.db import dispose_engine, get_session_factory
from app.db_models import OutboxRecord
from app.redis_client import close_redis, get_redis


class OutboxDispatcher:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        redis: Redis,
        settings: Settings,
    ) -> None:
        self._sessions = session_factory
        self._redis = redis
        self._settings = settings

    async def dispatch_batch(self, batch_size: int = 50) -> int:
        published = 0
        async with self._sessions() as session, session.begin():
            records = await session.scalars(
                select(OutboxRecord)
                .where(
                    OutboxRecord.published_at.is_(None),
                    OutboxRecord.available_at <= datetime.now(UTC),
                    OutboxRecord.payload["tenantId"].astext == self._settings.tenant_id,
                )
                .order_by(OutboxRecord.created_at)
                .limit(batch_size)
                .with_for_update(skip_locked=True)
            )
            for record in records:
                try:
                    await self._redis.xadd(self._settings.workflow_stream, record.payload)
                except Exception as exc:  # The durable row remains eligible for another dispatch.
                    record.publish_attempts += 1
                    record.last_error = f"{type(exc).__name__}: {exc}"[:2_000]
                    continue
                record.publish_attempts += 1
                record.published_at = datetime.now(UTC)
                record.last_error = None
                published += 1
        return published

    async def run_forever(self) -> None:
        while True:
            published = await self.dispatch_batch()
            if published == 0:
                await asyncio.sleep(self._settings.outbox_poll_interval_seconds)


async def _main() -> None:
    settings = get_settings()
    dispatcher = OutboxDispatcher(get_session_factory(), get_redis(), settings)
    try:
        await dispatcher.run_forever()
    finally:
        await close_redis()
        await dispose_engine()


if __name__ == "__main__":
    asyncio.run(_main())
