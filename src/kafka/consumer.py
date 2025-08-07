# src/services/ticket_consumer.py
import asyncio
import logging
import time
import json
from typing import Dict, Any, Optional
from aiokafka import AIOKafkaConsumer
from aiokafka.errors import KafkaError
from src.utils.kafka_config import kafka_config
from src.utils.cache import redis_client


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TicketResultConsumer:
    def __init__(self):
        self.consumer = None
        self.pending_results: Dict[str, Dict[str, Any]] = {}
        self.result_events: Dict[str, asyncio.Event] = {}
        self.running = False

    async def connect(self):
        """Initialize Kafka consumer for ticket results"""
        try:
            ticket_events_topic = kafka_config.get_ticket_events_topic()

            if not ticket_events_topic:
                logger.warning("Ticket events topic not found")
                return

            self.consumer = kafka_config.create_consumer(
                group_id='ticket-result-consumer',
                topics=ticket_events_topic
            )
            await self.consumer.start()
            logger.info("Ticket result consumer connected")
        except Exception as e:
            logger.error(f"Failed to connect result consumer: {e}")
            self.consumer = None

    async def start_consuming(self):
        """Start consuming ticket results in background"""
        if not self.consumer:
            await self.connect()
            if not self.consumer:
                logger.error("Result consumer not available")
                return

        logger.info("Starting ticket result consumer...")
        self.running = True

        try:
            async for message in self.consumer:
                if not self.running:
                    break

                try:
                    result_data = message.value
                    ticket_id = result_data.get('ticket_id')

                    if ticket_id:
                        # Store the result
                        self.pending_results[ticket_id] = result_data

                        # Notify waiting coroutines
                        if ticket_id in self.result_events:
                            self.result_events[ticket_id].set()

                        logger.info(
                            f"Received result for ticket {ticket_id}: {result_data.get('status')}")

                        # Also cache the result for future retrieval
                        await self.cache_ticket_result(ticket_id, result_data)

                except Exception as e:
                    logger.error(f"Error processing result message: {e}")

        except Exception as e:
            logger.error(f"Error in result consumer loop: {e}")
        finally:
            await self.cleanup()

    async def cache_ticket_result(self, ticket_id: str, result_data: Dict[str, Any]):
        """Cache ticket result for future retrieval"""
        try:
            if result_data.get('status') == 'success' and 'ticket_data' in result_data:
                ticket_data = result_data['ticket_data'].copy()
                if 'ticket_id' in ticket_data:
                    ticket_data['id'] = ticket_data.pop('ticket_id')

                ticket_data['_cached_type'] = 'TicketDetail'
                serialized = json.dumps(ticket_data, default=str)
                redis_client.setex(ticket_id, 3600, serialized)
            else:
                logger.info(f"Skipping cache for failed ticket result: {ticket_id}")
             # Cache for 1 hour
        except Exception as e:
            logger.error(f"Failed to cache result for ticket {ticket_id}: {e}")

    async def wait_for_ticket_result(self, ticket_id: str, timeout: int = 30) -> Optional[Dict[str, Any]]:
        """Wait for ticket processing result"""
        # Check if result is already available
        if ticket_id in self.pending_results:
            result = self.pending_results.pop(ticket_id)
            return result

        # Check cache first
        cached_result = await self.get_cached_result(ticket_id)
        if cached_result:
            return cached_result

        # Create event for this ticket
        if ticket_id not in self.result_events:
            self.result_events[ticket_id] = asyncio.Event()

        event = self.result_events[ticket_id]

        # Wait for result with timeout
        try:
            # Wait for result with timeout
            await asyncio.wait_for(event.wait(), timeout=timeout)

            if ticket_id in self.pending_results:
                result = self.pending_results.pop(ticket_id)
                # Clean up the event
                if ticket_id in self.result_events:
                    del self.result_events[ticket_id]
                return result

        except asyncio.TimeoutError:
            logger.warning(f"Timeout waiting for result of ticket {ticket_id}")

        # Clean up the event on timeout
        if ticket_id in self.result_events:
            del self.result_events[ticket_id]

        return None

    async def get_cached_result(self, ticket_id: str) -> Optional[Dict[str, Any]]:
        """Get cached ticket result"""
        try:
            cached_data = redis_client.get(ticket_id)
            if cached_data:
                return json.loads(cached_data)
        except Exception as e:
            logger.error(f"Error getting cached result for ticket {ticket_id}: {e}")
        return None

    async def cleanup(self):
        """Clean up resources"""
        self.running = False
        if self.consumer:
            await self.consumer.stop()
        logger.info("Ticket result consumer cleaned up")


# Global consumer instance
ticket_result_consumer = TicketResultConsumer()