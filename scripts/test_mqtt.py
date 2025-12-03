#!/usr/bin/env python3
"""Test MQTT -> Kafka ingestion."""
import json
import os
import time
import uuid

from kafka import KafkaConsumer, TopicPartition
from kafka.errors import NoBrokersAvailable
import paho.mqtt.client as mqtt

BROKER_HOST = os.environ.get("MQTT_HOST", "127.0.0.1")
BROKER_PORT = int(os.environ.get("MQTT_PORT", "1884"))
DEVICE_ID = os.environ.get("MQTT_DEVICE_ID", "VALVE-001")
TOPIC = os.environ.get(
    "MQTT_TOPIC", f"devices/{DEVICE_ID}/telemetry"
)
KAFKA_BOOTSTRAP = os.environ.get("KAFKA_BOOTSTRAP", "127.0.0.1:29092")
RAW_TOPIC = os.environ.get("MQTT_KAFKA_TOPIC", "raw_telemetry")
TIMEOUT = int(os.environ.get("MQTT_TEST_TIMEOUT", "10"))


def publish_message(nonce: str):
    payload = {
        "level": 77.2,
        "temperature": 26.4,
        "pressure": 1.25,
        "battery": 82,
        "test_source": "mqtt_test",
        "nonce": nonce,
    }
    print(
        f"Publishing MQTT telemetry to {BROKER_HOST}:{BROKER_PORT} topic '{TOPIC}': {payload}"
    )
    
    published = False
    publish_error = None
    
    def on_connect(client, userdata, flags, rc):
        if rc == 0:
            print(f"Connected to MQTT broker (rc={rc})")
        else:
            print(f"Failed to connect to MQTT broker (rc={rc})")
    
    def on_publish(client, userdata, mid):
        nonlocal published
        published = True
        print(f"Message published (mid={mid})")
    
    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_publish = on_publish
    
    try:
        print(f"Connecting to MQTT broker {BROKER_HOST}:{BROKER_PORT}...")
        client.connect(BROKER_HOST, BROKER_PORT, 60)
        client.loop_start()
        
        # Wait for connection
        timeout = 5
        start = time.time()
        while not client.is_connected() and (time.time() - start) < timeout:
            time.sleep(0.1)
        
        if not client.is_connected():
            raise Exception(f"Failed to connect to MQTT broker within {timeout}s")
        
        # Publish message
        print(f"Publishing to topic '{TOPIC}'...")
        info = client.publish(TOPIC, json.dumps(payload), qos=1)
        
        # Wait for publish with timeout
        timeout = 5
        start = time.time()
        while not published and (time.time() - start) < timeout:
            time.sleep(0.1)
        
        if not published:
            raise Exception(f"Message not published within {timeout}s")
        
        print("MQTT message published successfully")
        
    except Exception as e:
        print(f"ERROR publishing MQTT message: {e}")
        raise
    finally:
        client.loop_stop()
        client.disconnect()
        print("Disconnected from MQTT broker")


def find_message_in_kafka(nonce: str):
    """Find message with matching nonce by reading recent messages."""
    print(f"Connecting to Kafka at {KAFKA_BOOTSTRAP}...")
    try:
        consumer = KafkaConsumer(
            bootstrap_servers=KAFKA_BOOTSTRAP,
            enable_auto_commit=False,
            value_deserializer=lambda m: json.loads(m.decode()),
            consumer_timeout_ms=2000,
        )
        
        # Get partition info
        partitions = consumer.partitions_for_topic(RAW_TOPIC)
        if not partitions:
            print(f"ERROR: Topic '{RAW_TOPIC}' not found or has no partitions")
            consumer.close()
            return False
        
        print(f"Found {len(partitions)} partition(s) for topic '{RAW_TOPIC}'")
        
        # Assign partitions and get end offsets
        topic_partitions = [TopicPartition(RAW_TOPIC, p) for p in partitions]
        consumer.assign(topic_partitions)
        
        # Get end offsets
        end_offsets = consumer.end_offsets(topic_partitions)
        print(f"End offsets: {dict(end_offsets)}")
        
        # Read last 100 messages from each partition
        for tp in topic_partitions:
            end_offset = end_offsets[tp]
            start_offset = max(0, end_offset - 100)  # Read last 100 messages
            consumer.seek(tp, start_offset)
            print(f"Reading messages from partition {tp.partition}, offset {start_offset} to {end_offset}")
        
        # Poll for messages
        deadline = time.time() + TIMEOUT
        messages_checked = 0
        
        while time.time() < deadline:
            records = consumer.poll(timeout_ms=500)
            if records:
                for partition_records in records.values():
                    for msg in partition_records:
                        messages_checked += 1
                        value = msg.value
                        
                        msg_nonce = value.get("payload", {}).get("nonce", "")
                        msg_device = value.get("device_id", "")
                        
                        # Check if this is our message
                        if msg_device == DEVICE_ID and msg_nonce == nonce:
                            print(f"SUCCESS: Found message after checking {messages_checked} message(s)!")
                            print(json.dumps(value, indent=2))
                            consumer.close()
                            return True
                        
                        # Stop if we've read past the end offset
                        if msg.offset >= end_offsets[TopicPartition(RAW_TOPIC, msg.partition)] - 1:
                            break
            
            # If we've checked enough messages or reached end, stop
            if messages_checked > 200:  # Safety limit
                break
        
        print(f"FAILED: Checked {messages_checked} recent messages but did not find nonce '{nonce}'")
        consumer.close()
        return False
        
    except NoBrokersAvailable as exc:
        print(f"Failed to connect to Kafka at {KAFKA_BOOTSTRAP}: {exc}")
        return False
    except Exception as e:
        print(f"Error reading from Kafka: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    nonce = str(uuid.uuid4())
    
    # Publish MQTT message first
    print(f"Publishing MQTT message with nonce: {nonce}")
    publish_message(nonce)
    
    # Wait for backend to process and publish to Kafka
    print("Waiting for backend to process MQTT message...")
    time.sleep(2)  # Give backend time to bridge to Kafka
    
    # Search for the message in Kafka
    print(f"Searching for message with nonce '{nonce}' in Kafka topic '{RAW_TOPIC}'...")
    success = find_message_in_kafka(nonce)
    
    if success:
        print("✅ Test PASSED!")
    else:
        print("❌ Test FAILED!")


if __name__ == "__main__":
    main()
