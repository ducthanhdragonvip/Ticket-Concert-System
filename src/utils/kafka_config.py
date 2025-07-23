import os
from kafka import KafkaProducer, KafkaConsumer
import json
from typing import Dict, Any
import logging

from src.utils.config import Settings

logger = logging.getLogger(__name__)

class KafkaConfig:
    def __init__(self):
        self.bootstrap_servers = Settings.KAFKA_BOOTSTRAP_SERVERS
        self.ticket_orders_topic = 'ticket-orders'
        self.ticket_events_topic = 'ticket-events'

    def create_producer(self) -> KafkaProducer:
        return KafkaProducer(
            bootstrap_servers=self.bootstrap_servers,
            value_serializer=lambda v: json.dumps(v).encode('utf-8'),
            key_serializer=lambda k: k.encode('utf-8') if k else None,
            acks='all',  # Wait for all replicas to acknowledge
            retries=3,
            retry_backoff_ms=100,
            request_timeout_ms=30000,
            batch_size=16384,
            linger_ms=10
        )

    def create_consumer(self, group_id: str, topics: list) -> KafkaConsumer:
        return KafkaConsumer(
            *topics,
            bootstrap_servers=self.bootstrap_servers,
            group_id=group_id,
            value_deserializer=lambda m: json.loads(m.decode('utf-8')),
            key_deserializer=lambda k: k.decode('utf-8') if k else None,
            auto_offset_reset='latest',
            enable_auto_commit=True,
            auto_commit_interval_ms=1000,
            session_timeout_ms=30000,
            heartbeat_interval_ms=10000,
            max_poll_records=100,
            consumer_timeout_ms=1000
        )


# Global Kafka configuration instance
kafka_config = KafkaConfig()

# Event schemas
class TicketOrderEvent:
    def __init__(self, ticket_id: str, zone_id: str, user_id: str = None, timestamp: float = None):
        import time
        self.ticket_id = ticket_id
        self.zone_id = zone_id
        # self.user_id = user_id
        self.timestamp = timestamp or time.time()
        self.status = 'pending'

    def to_dict(self) -> Dict[str, Any]:
        return {
            'ticket_id': self.ticket_id,
            'zone_id': self.zone_id,
            # 'user_id': self.user_id,
            'timestamp': self.timestamp,
            'status': self.status
        }


class TicketResultEvent:
    def __init__(self, ticket_id: str, status: str, message: str = None,
                 ticket_data: Dict[str, Any] = None, error: str = None):
        import time
        # self.ticket_id = ticket_id
        self.status = status  # 'success', 'failed', 'invalid'
        self.message = message
        self.ticket_data = ticket_data
        self.error = error
        self.timestamp = time.time()

    def to_dict(self) -> Dict[str, Any]:
        return {
            # 'ticket_id': self.ticket_id,
            'status': self.status,
            'message': self.message,
            'ticket_data': self.ticket_data,
            'error': self.error,
            'timestamp': self.timestamp
        }
