import os
from kafka import KafkaProducer, KafkaConsumer, KafkaAdminClient
import json
from typing import Dict, Any, List
import logging

from kafka.admin import NewTopic

from src.utils.config import Settings

logger = logging.getLogger(__name__)

class KafkaConfig:
    def __init__(self):
        self.bootstrap_servers = Settings.KAFKA_BOOTSTRAP_SERVERS
        self.ticket_orders_topic = 'ticket-orders'
        self.ticket_events_topic = 'ticket-events'
        self.admin_client = None

    def get_admin_client(self) -> KafkaAdminClient:
        """Get or create Kafka admin client for topic management"""
        if not self.admin_client:
            self.admin_client = KafkaAdminClient(
                bootstrap_servers=self.bootstrap_servers,
                client_id='ticket-admin'
            )
        return self.admin_client

    def get_concert_order_topic(self, concert_id: str) -> str:
        return f"ticket-orders-{concert_id}"

    def get_concert_events_topic(self, concert_id: str) -> str:
        return f"ticket-events-{concert_id}"

    def create_concert_topics(self, concert_id: str, num_partitions: int = 3, replication_factor: int = 1):
        """Create topics for a specific concert"""
        try:
            admin_client = self.get_admin_client()

            # Define topics for the concert
            topics = [
                NewTopic(
                    name=self.get_concert_order_topic(concert_id),
                    num_partitions=num_partitions,
                    replication_factor=replication_factor
                ),
                NewTopic(
                    name=self.get_concert_events_topic(concert_id),
                    num_partitions=num_partitions,
                    replication_factor=replication_factor
                )
            ]

            # Create topics
            result = admin_client.create_topics(topics, validate_only=False)

            # Wait for topics to be created
            for topic_name, future in result.items():
                try:
                    future.result()  # The result itself is None
                    logger.info(f"Topic {topic_name} created successfully")
                except Exception as e:
                    if "TopicExistsException" in str(e):
                        logger.info(f"Topic {topic_name} already exists")
                    else:
                        logger.error(f"Failed to create topic {topic_name}: {e}")

        except Exception as e:
            logger.error(f"Error creating topics for concert {concert_id}: {e}")

    def list_all_topics(self) -> List[str]:
        """List all concert-specific topics"""
        try:
            admin_client = self.get_admin_client()
            metadata = admin_client.describe_topics()

            concert_topics = []
            for topic_name in metadata.keys():
                if topic_name.startswith('ticket-orders-') or topic_name.startswith('ticket-events-'):
                    concert_topics.append(topic_name)

            return concert_topics
        except Exception as e:
            logger.error(f"Error listing concert topics: {e}")
            return []

    def get_ticket_orders_topic(self) -> List[str]:
        """Get the main ticket orders topic"""
        try:
            admin_client = self.get_admin_client()
            topics = admin_client.list_topics()

            ticket_order_topics = []
            for topic_name in topics:
                if  topic_name.startswith('ticket-orders-'):
                    ticket_order_topics.append(topic_name)
            print(ticket_order_topics)

            return ticket_order_topics
        except Exception as e:
            logger.error(f"Error getting ticket orders topic: {e}")
            return []

    def get_ticket_events_topic(self) -> List[str]:
        """Get the main ticket events topic"""
        try:
            admin_client = self.get_admin_client()
            topics = admin_client.list_topics()

            ticket_event_topics = []
            for topic_name in topics:
                if topic_name.startswith('ticket-events-'):
                    ticket_event_topics.append(topic_name)

            return ticket_event_topics
        except Exception as e:
            logger.error(f"Error getting ticket events topic: {e}")
            return []

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

    def create_concert_consumer(self, concert_id: str, group_id: str = None) -> KafkaConsumer:
        """Create consumer for specific concert topics"""
        if not group_id:
            group_id = f'concert-{concert_id}-consumer'

        topics = [
            self.get_concert_order_topic(concert_id),
            self.get_concert_events_topic(concert_id)
        ]

        return self.create_consumer(group_id, topics)


# Global Kafka configuration instance
kafka_config = KafkaConfig()

# Event schemas
class TicketOrderEvent:
    def __init__(self, ticket_id: str, zone_id: str, concert_id: str ,user_id: str = None, timestamp: float = None):
        import time
        self.ticket_id = ticket_id
        self.zone_id = zone_id
        self.concert_id = concert_id
        # self.user_id = user_id
        self.timestamp = timestamp or time.time()
        self.status = 'pending'

    def to_dict(self) -> Dict[str, Any]:
        return {
            'ticket_id': self.ticket_id,
            'zone_id': self.zone_id,
            'concert_id': self.concert_id,
            # 'user_id': self.user_id,
            'timestamp': self.timestamp,
            'status': self.status
        }


class TicketResultEvent:
    def __init__(self, ticket_id: str,zone_id: str ,concert_id: str,status: str, message: str = None,
                 ticket_data: Dict[str, Any] = None, error: str = None):
        import time
        self.ticket_id = ticket_id
        self.zone_id = zone_id
        self.concert_id = concert_id
        self.status = status  # 'success', 'failed', 'invalid'
        self.message = message
        self.ticket_data = ticket_data
        self.error = error
        self.timestamp = time.time()

    def to_dict(self) -> Dict[str, Any]:
        return {
            'ticket_id': self.ticket_id,
            'zone_id': self.zone_id,
            'concert_id': self.concert_id,
            'status': self.status,
            'message': self.message,
            'ticket_data': self.ticket_data,
            'error': self.error,
            'timestamp': self.timestamp
        }
