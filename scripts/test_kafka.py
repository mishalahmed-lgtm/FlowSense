#!/usr/bin/env python3
"""Quick Kafka connectivity test."""
import json
import os
import time

from kafka import KafkaProducer, KafkaConsumer
from kafka.errors import KafkaTimeoutError, NoBrokersAvailable

BOOTSTRAP = os.environ.get("KAFKA_BOOTSTRAP", "127.0.0.1:29092")
TEST_TOPIC = os.environ.get("KAFKA_TEST_TOPIC", "kafka_connectivity_test")
TIMEOUT = int(os.environ.get("KAFKA_TEST_TIMEOUT", "5"))


def test_kafka():
    print(f"Using Kafka bootstrap servers: {BOOTSTRAP}")
    producer = KafkaProducer(
        bootstrap_servers=BOOTSTRAP,
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
        request_timeout_ms=5000,
        api_version_auto_timeout_ms=5000,
    )
    consumer = KafkaConsumer(
        TEST_TOPIC,
        bootstrap_servers=BOOTSTRAP,
        auto_offset_reset="earliest",
        enable_auto_commit=False,
        consumer_timeout_ms=500,
        value_deserializer=lambda v: json.loads(v.decode("utf-8")),
    )

    payload = {"message": "kafka connectivity check", "timestamp": time.time()}
    print(f"Publishing test message to '{TEST_TOPIC}': {payload}")

    future = producer.send(TEST_TOPIC, payload)
    record_metadata = future.get(timeout=5)
    print(
        "Published to",
        record_metadata.topic,
        f"partition={record_metadata.partition}",
        f"offset={record_metadata.offset}",
    )
    producer.flush()

    deadline = time.time() + TIMEOUT
    try:
        while time.time() < deadline:
            records = consumer.poll(timeout_ms=500)
            for partition_records in records.values():
                for msg in partition_records:
                    print("Received message from Kafka:", msg.value)
                    return True
            time.sleep(0.2)
        print("Did not receive the test message within timeout.")
        return False
    finally:
        producer.close()
        consumer.close()


def main():
    try:
        success = test_kafka()
        if not success:
            raise KafkaTimeoutError("Kafka poll timed out")
    except (KafkaTimeoutError, NoBrokersAvailable) as exc:
        print(f"Kafka test failed: {exc}")
    except Exception as exc:
        print(f"Unexpected error: {exc}")


if __name__ == "__main__":
    main()
