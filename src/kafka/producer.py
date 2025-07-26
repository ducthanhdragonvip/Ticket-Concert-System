import asyncio
import logging
from typing import Dict, Any
from kafka import KafkaProducer
from kafka.errors import KafkaError
from src.utils.kafka_config import kafka_config, TicketOrderEvent, TicketResultEvent

logger = logging.getLogger(__name__)


class TicketKafkaProducer:
    def __init__(self):
        self.producer = None
        self.connect()

    def connect(self):
        """Initialize Kafka producer connection"""
        try:
            self.producer = kafka_config.create_producer()
            logger.info("Kafka producer connected successfully")
        except Exception as e:
            logger.error(f"Failed to connect to Kafka: {e}")
            self.producer = None

    async def produce_ticket_order(self, ticket_order: TicketOrderEvent) -> bool:
        """Produce ticket order to ticket-orders topic"""
        if not self.producer:
            self.connect()
            if not self.producer:
                logger.error("Kafka producer not available")
                return False

        try:
            topic = kafka_config.get_concert_order_topic(ticket_order.concert_id)

            # Send the message
            future = self.producer.send(
                topic,
                key=ticket_order.ticket_id,
                value=ticket_order.to_dict()
            )

            # Wait for the message to be sent
            record_metadata = future.get(timeout=10)
            logger.info(f"Ticket order sent to topic {record_metadata.topic} "
                        f"partition {record_metadata.partition} "
                        f"offset {record_metadata.offset}"
                        f"for concert {ticket_order.concert_id}")
            return True

        except KafkaError as e:
            logger.error(f"Failed to send ticket order to Kafka: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error sending ticket order: {e}")
            return False

    async def produce_ticket_result(self, ticket_result: TicketResultEvent) -> bool:
        """Produce ticket result to ticket-events topic"""
        if not self.producer:
            self.connect()
            if not self.producer:
                logger.error("Kafka producer not available")
                return False

        try:
            topic = kafka_config.get_concert_events_topic(ticket_result.concert_id)

            future = self.producer.send(
                topic,
                key=ticket_result.ticket_id,
                value=ticket_result.to_dict()
            )

            record_metadata = future.get(timeout=10)
            logger.info(f"Ticket result sent to topic {record_metadata.topic} "
                        f"partition {record_metadata.partition} "
                        f"offset {record_metadata.offset}")
            return True

        except KafkaError as e:
            logger.error(f"Failed to send ticket result to Kafka: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error sending ticket result: {e}")
            return False

    def close(self):
        """Close the producer connection"""
        if self.producer:
            self.producer.close()
            logger.info("Kafka producer closed")


# Global producer instance
ticket_producer = TicketKafkaProducer()