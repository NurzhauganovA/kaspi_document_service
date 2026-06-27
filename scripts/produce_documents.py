#!/usr/bin/env python3
"""
Produce test documents into Kafka input topic.

Usage (inside Docker, uses kafka:9092 from .env automatically):
    python scripts/produce_documents.py --count 100

Usage (from host machine):
    python scripts/produce_documents.py --count 100 --kafka localhost:29092
"""
import argparse
import asyncio
import json
import os
import random
import sys
import uuid
from datetime import (
    datetime,
    timezone,
)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from aiokafka import AIOKafkaProducer

from app.core.config import settings


async def produce(count: int, bootstrap: str, topic: str) -> None:
    producer = AIOKafkaProducer(
        bootstrap_servers=bootstrap,
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
    )
    await producer.start()
    print(f"Producing {count} documents to {topic} via {bootstrap}...")

    try:
        for i in range(count):
            doc = {
                "id": str(uuid.uuid4()),
                "type": random.choice(["invoice", "contract", "report", "receipt"]),
                "amount": round(random.uniform(100, 100000), 2),
                "currency": random.choice(["USD", "EUR", "RUB"]),
                "created_by": f"system_{random.randint(1, 10)}",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "metadata": {"batch": i // 100, "priority": random.randint(1, 5)},
            }
            await producer.send(topic, value=doc, key=doc["id"].encode("utf-8"))

            if (i + 1) % 100 == 0:
                print(f"  Sent {i + 1}/{count}")

        await producer.flush()
        print(f"✓ Done — {count} documents sent")

    finally:
        await producer.stop()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, default=500, help="Number of documents to produce")
    parser.add_argument(
        "--kafka",
        default=settings.KAFKA_BOOTSTRAP_SERVERS,
        help=f"Kafka bootstrap (default: {settings.KAFKA_BOOTSTRAP_SERVERS})",
    )
    parser.add_argument(
        "--topic",
        default=settings.KAFKA_INPUT_TOPIC,
        help=f"Input topic (default: {settings.KAFKA_INPUT_TOPIC})",
    )
    args = parser.parse_args()

    asyncio.run(produce(args.count, args.kafka, args.topic))
