# src/services/ticket_consumer.py
import asyncio
import logging
import time
import json
from typing import Dict, Any, Optional
from kafka import KafkaConsumer
from kafka.errors import KafkaError
from src.utils.kafka_config import kafka_config
from src.utils.cache import redis_client
from concurrent.futures import ThreadPoolExecutor
import threading

logger = logging.getLogger(__name__)


class TicketResultConsumer:
    def __init__(self):
        self.consumer = None
        self.pending_results: Dict[str, Dict[str, Any]] = {}
        self.result_locks: Dict[str, threading.Event] = {}
        self.running = False
        self.executor = ThreadPoolExecutor(max_workers=5)

    def connect(self):
        """Initialize Kafka consumer for ticket results"""
        try:
            self.consumer = kafka_config.create_consumer(
                group_id='ticket-result-consumer',
                topics=[kafka_config.ticket_events_topic]
            )
            logger.info("Ticket result consumer connected")
        except Exception as e:
            logger.error(f"Failed to connect result consumer: {e}")
            self.consumer = None

    def start_consuming(self):
        """Start consuming ticket results in background"""
        if not self.consumer:
            self.connect()
            if not self.consumer:
                logger.error("Result consumer not available")
                return

        logger.info("Starting ticket result consumer...")
        self.running = True

        def consume_loop():
            try:
                while self.running:
                    try:
                        # Poll for messages
                        message_batch = self.consumer.poll(timeout_ms=1000)

                        for topic_partition, messages in message_batch.items():
                            for message in messages:
                                try:
                                    result_data = message.value
                                    ticket_id = result_data.get('ticket_id')

                                    if ticket_id:
                                        # Store the result
                                        self.pending_results[ticket_id] = result_data

                                        # Notify waiting threads
                                        if ticket_id in self.result_locks:
                                            self.result_locks[ticket_id].set()

                                        logger.info(
                                            f"Received result for ticket {ticket_id}: {result_data.get('status')}")

                                        # Also cache the result for future retrieval
                                        self.cache_ticket_result(ticket_id, result_data)

                                except Exception as e:
                                    logger.error(f"Error processing result message: {e}")

                    except Exception as e:
                        logger.error(f"Error in result consumer loop: {e}")
                        time.sleep(1)

            except KeyboardInterrupt:
                logger.info("Result consumer shutting down...")
            finally:
                if self.consumer:
                    self.consumer.close()

        # Run consumer in executor to avoid blocking
        self.executor.submit(consume_loop)

    def cache_ticket_result(self, ticket_id: str, result_data: Dict[str, Any]):
        """Cache ticket result for future retrieval"""
        try:
            if result_data.get('status') == 'success' and 'ticket_data' in result_data:
                ticket_data = result_data['ticket_data'].copy()
                if 'ticket_id' in ticket_data:
                    ticket_data['id'] = ticket_data.pop('ticket_id')

                ticket_data['_cached_type'] = 'TicketDetail'

            serialized = json.dumps(ticket_data, default=str)
            redis_client.setex(ticket_id, 3600, serialized)  # Cache for 1 hour
        except Exception as e:
            logger.error(f"Failed to cache result for ticket {ticket_id}: {e}")

    async def wait_for_ticket_result(self, ticket_id: str, timeout: int = 30) -> Optional[Dict[str, Any]]:
        """Wait for ticket processing result"""
        # Check if result is already available
        if ticket_id in self.pending_results:
            result = self.pending_results.pop(ticket_id)
            return result

        # Check cache first
        cached_result = self.get_cached_result(ticket_id)
        if cached_result:
            return cached_result

        # Create event for this ticket
        if ticket_id not in self.result_locks:
            self.result_locks[ticket_id] = threading.Event()

        event = self.result_locks[ticket_id]

        # Wait for result with timeout
        def wait_for_result():
            return event.wait(timeout)

        # Run the wait in executor to avoid blocking
        result_available = await asyncio.get_event_loop().run_in_executor(
            self.executor, wait_for_result
        )

        if result_available and ticket_id in self.pending_results:
            result = self.pending_results.pop(ticket_id)
            # Clean up the event
            if ticket_id in self.result_locks:
                del self.result_locks[ticket_id]
            return result

        # Clean up the event on timeout
        if ticket_id in self.result_locks:
            del self.result_locks[ticket_id]

        logger.warning(f"Timeout waiting for result of ticket {ticket_id}")
        return None

    def get_cached_result(self, ticket_id: str) -> Optional[Dict[str, Any]]:
        """Get cached ticket result"""
        try:
            cached_data = redis_client.get(ticket_id)
            if cached_data:
                return json.loads(cached_data)
        except Exception as e:
            logger.error(f"Error getting cached result for ticket {ticket_id}: {e}")
        return None

    def cleanup(self):
        """Clean up resources"""
        self.running = False
        if self.consumer:
            self.consumer.close()
        self.executor.shutdown(wait=True)
        logger.info("Ticket result consumer cleaned up")


# Global consumer instance
ticket_result_consumer = TicketResultConsumer()


# Auto-start the consumer when module is imported
def initialize_consumer():
    """Initialize consumer on module import"""
    try:
        ticket_result_consumer.start_consuming()
        logger.info("Ticket result consumer initialized")
    except Exception as e:
        logger.error(f"Failed to initialize consumer: {e}")


# Initialize on import
initialize_consumer()