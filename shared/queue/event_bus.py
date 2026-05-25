"""
Event Bus — RabbitMQ for production, in-memory fallback for development.
Publishes events to RabbitMQ topic exchange so downstream pipeline consumers
(screening, outreach, interview) can subscribe to events like profile.parsed.
"""
import asyncio
import json
from datetime import datetime
from typing import Callable, Any
from collections import defaultdict

from config import RABBITMQ_URL

# Try to import aio-pika for RabbitMQ support
try:
    import aio_pika
    HAS_AIOPIKA = True
except ImportError:
    HAS_AIOPIKA = False


# ═══════════════════════════════════════════════════════════
# In-Memory Event Bus (fallback when RabbitMQ is unavailable)
# ═══════════════════════════════════════════════════════════

class InMemoryEventBus:
    """Async in-memory event bus — used when RabbitMQ is not running."""

    def __init__(self):
        self._subscribers: dict[str, list[Callable]] = defaultdict(list)
        self._event_log: list[dict] = []

    async def connect(self):
        print("📡 Using in-memory event bus (RabbitMQ not available)")

    async def close(self):
        pass

    @property
    def is_connected(self) -> bool:
        return True

    @property
    def backend(self) -> str:
        return "in-memory"

    def subscribe(self, topic: str, handler: Callable):
        self._subscribers[topic].append(handler)

    async def publish(self, topic: str, payload: dict, agent: str = "system"):
        event = {
            "topic": topic,
            "payload": payload,
            "agent": agent,
            "timestamp": datetime.utcnow().isoformat(),
        }
        self._event_log.append(event)
        print(f"📨 In-Memory [{topic}] from {agent}: {json.dumps(payload, default=str)[:200]}")

        for handler in self._subscribers.get(topic, []):
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(payload)
                else:
                    handler(payload)
            except Exception as e:
                print(f"❌ Handler error on {topic}: {e}")

    def get_log(self, limit: int = 50) -> list[dict]:
        return list(reversed(self._event_log[-limit:]))


# ═══════════════════════════════════════════════════════════
# RabbitMQ Event Bus (production — real message broker)
# ═══════════════════════════════════════════════════════════

class RabbitMQEventBus:
    """
    Real RabbitMQ event bus using aio-pika.
    Publishes to a topic exchange 'recruitment.events'.
    Downstream consumers bind queues to routing keys like 'profile.parsed'.
    """

    EXCHANGE_NAME = "recruitment.events"

    def __init__(self, url: str):
        self._url = url
        self._connection = None
        self._channel = None
        self._exchange = None
        self._subscribers: dict[str, list[Callable]] = defaultdict(list)
        self._event_log: list[dict] = []
        self._connected = False

    async def connect(self):
        """Connect to RabbitMQ and declare the topic exchange."""
        try:
            self._connection = await aio_pika.connect_robust(self._url)
            self._channel = await self._connection.channel()
            await self._channel.set_qos(prefetch_count=10)

            # Declare the topic exchange (durable survives broker restart)
            self._exchange = await self._channel.declare_exchange(
                self.EXCHANGE_NAME,
                aio_pika.ExchangeType.TOPIC,
                durable=True,
            )
            self._connected = True
            print(f"✅ Connected to RabbitMQ at {self._url}")

            # Bind any handlers that were registered before connection
            for topic, handlers in self._subscribers.items():
                for handler in handlers:
                    await self._bind_consumer(topic, handler)

        except Exception as e:
            self._connected = False
            print(f"⚠️ RabbitMQ connection failed: {e}")
            print("   Events will be published in-memory and logged locally.")

    async def close(self):
        """Gracefully close the RabbitMQ connection."""
        if self._connection and not self._connection.is_closed:
            await self._connection.close()
            self._connected = False
            print("👋 RabbitMQ connection closed")

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    def backend(self) -> str:
        return "rabbitmq" if self._connected else "in-memory-fallback"

    async def _bind_consumer(self, topic: str, handler: Callable):
        """Bind a consumer queue to the exchange for a specific topic."""
        if not self._connected or not self._channel:
            return

        # Create a durable queue named after the topic
        queue_name = f"recruitment.{topic.replace('.', '_')}"
        queue = await self._channel.declare_queue(queue_name, durable=True)
        await queue.bind(self._exchange, routing_key=topic)

        async def on_message(message: aio_pika.IncomingMessage):
            async with message.process():
                try:
                    payload = json.loads(message.body)
                    if asyncio.iscoroutinefunction(handler):
                        await handler(payload)
                    else:
                        handler(payload)
                except Exception as e:
                    print(f"❌ RabbitMQ consumer error on {topic}: {e}")

        await queue.consume(on_message)
        print(f"   📌 Queue '{queue_name}' bound to '{topic}'")

    def subscribe(self, topic: str, handler: Callable):
        """Register a handler for a topic. If connected, binds immediately."""
        self._subscribers[topic].append(handler)
        if self._connected:
            asyncio.create_task(self._bind_consumer(topic, handler))

    async def publish(self, topic: str, payload: dict, agent: str = "system"):
        """Publish an event. Goes to RabbitMQ if connected, in-memory otherwise."""
        event = {
            "topic": topic,
            "payload": payload,
            "agent": agent,
            "timestamp": datetime.utcnow().isoformat(),
        }
        self._event_log.append(event)

        if self._connected and self._exchange:
            # ── Publish to RabbitMQ ──
            message = aio_pika.Message(
                body=json.dumps(payload, default=str).encode(),
                content_type="application/json",
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
                headers={"agent": agent, "topic": topic},
                timestamp=datetime.utcnow(),
            )
            await self._exchange.publish(message, routing_key=topic)
            print(f"📨 RabbitMQ [{topic}] from {agent}: {json.dumps(payload, default=str)[:200]}")
        else:
            # ── Fallback: in-memory dispatch ──
            print(f"📨 Fallback [{topic}] from {agent}: {json.dumps(payload, default=str)[:200]}")
            for handler in self._subscribers.get(topic, []):
                try:
                    if asyncio.iscoroutinefunction(handler):
                        await handler(payload)
                    else:
                        handler(payload)
                except Exception as e:
                    print(f"❌ Handler error on {topic}: {e}")

    def get_log(self, limit: int = 50) -> list[dict]:
        return list(reversed(self._event_log[-limit:]))


# ═══════════════════════════════════════════════════════════
# Factory & Global Singleton
# ═══════════════════════════════════════════════════════════

def _create_event_bus():
    """Create the appropriate event bus based on available infrastructure."""
    if HAS_AIOPIKA and RABBITMQ_URL:
        print("🐰 RabbitMQ client available — will connect on startup")
        return RabbitMQEventBus(RABBITMQ_URL)
    if not HAS_AIOPIKA:
        print("⚠️ aio-pika not installed — using in-memory event bus")
    return InMemoryEventBus()


# Global singleton — used by all agents
event_bus = _create_event_bus()
