import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any

from aiokafka import AIOKafkaConsumer, AIOKafkaProducer

from app.config import settings

logger = logging.getLogger(__name__)

class EventPublisher:
    def __init__(self) -> None:
        self._producer: AIOKafkaProducer | None = None

    async def start(self) -> None:
        try:
            self._producer = AIOKafkaProducer(
                bootstrap_servers=settings.kafka_bootstrap_servers,
                value_serializer=lambda v: json.dumps(v).encode("utf-8"),
            )
            await self._producer.start()
        except Exception as exc:
            logger.warning("Kafka producer startup failed: %s", exc)
            if self._producer:
                await self._producer.stop()
            self._producer = None

    async def stop(self) -> None:
        if self._producer:
            await self._producer.stop()
            self._producer = None

    async def publish(self, topic: str, event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
        event = {
            "topic": topic,
            "event_type": event_type,
            "published_at": datetime.now(timezone.utc).isoformat(),
            "payload": payload,
        }
        if self._producer:
            await self._producer.send_and_wait(settings.kafka_events_topic, event)
        else:
            logger.warning("Kafka producer unavailable; event not sent to broker: %s", event_type)
        return event


class EventConsumer:
    def __init__(self) -> None:
        self._consumer: AIOKafkaConsumer | None = None
        self._task: asyncio.Task[Any] | None = None

    async def start(self) -> None:
        try:
            self._consumer = AIOKafkaConsumer(
                settings.kafka_events_topic,
                bootstrap_servers=settings.kafka_bootstrap_servers,
                group_id=settings.kafka_consumer_group,
                value_deserializer=lambda v: json.loads(v.decode("utf-8")),
            )
            await self._consumer.start()
            self._task = asyncio.create_task(self._consume_loop())
        except Exception as exc:
            logger.warning("Kafka consumer startup failed: %s", exc)
            if self._consumer:
                await self._consumer.stop()
            self._consumer = None

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            self._task = None
        if self._consumer:
            await self._consumer.stop()
            self._consumer = None

    async def _consume_loop(self) -> None:
        assert self._consumer is not None
        try:
            async for message in self._consumer:
                logger.info("Consumed event: %s", message.value)
        except asyncio.CancelledError:
            logger.info("Kafka consumer loop stopped")
