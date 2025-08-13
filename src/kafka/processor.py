import asyncio
import logging
import time
import json
from typing import Dict, Any, List
from datetime import datetime

from src.repositories import zone_repository, concert_repository
from src.utils.cache import update_cache
from src.utils.database import db_session_context, get_db, SessionLocal, Base, engine
from src.utils.kafka_config import kafka_config, TicketResultEvent
from src.kafka.producer import ticket_producer
from src.dto.ticket import TicketDetail
from src.entities.ticket import Ticket
from src.entities.zone import Zone
from src.entities.concert import Concert
from src.utils.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TicketProcessor:
    def __init__(self):
        self.consumer = None
        self.ticket_queue = asyncio.Queue()
        self.batch_timeout = settings.BATCH_TIMEOUT
        self.running = False
        self.batch_task = None

    async def connect(self):
        """Initialize Kafka consumer"""
        try:
            ticket_orders_topic = kafka_config.get_ticket_orders_topic()
            logger.info(ticket_orders_topic)
            if not ticket_orders_topic:
                logger.warning("Concert order topic not found")
                return

            self.consumer = kafka_config.create_consumer(
                group_id='ticket-processor',
                topics=ticket_orders_topic
            )
            await self.consumer.start()
            logger.info("Ticket processor consumer connected")
        except Exception as e:
            logger.error(f"Failed to connect consumer: {e}")
            self.consumer = None

    async def start_batch_processor(self):
        """Background task to handle batch processing from queue"""
        pending_tickets = []
        last_batch_time = time.time()

        while self.running:
            try:
                # Wait for items with timeout
                ticket_info = await asyncio.wait_for(
                    self.ticket_queue.get(),
                    timeout=1.0
                )
                pending_tickets.append(ticket_info)
                self.ticket_queue.task_done()

                current_time = time.time()

                # Process batch only if timeout reached AND we have tickets
                # Remove the queue.empty() check to allow accumulation
                if current_time - last_batch_time >= self.batch_timeout:
                    if pending_tickets:
                        await self.batch_persist_tickets(pending_tickets)
                        pending_tickets.clear()
                        last_batch_time = current_time

            except asyncio.TimeoutError:
                # Check if we should process pending tickets due to timeout
                current_time = time.time()
                if (pending_tickets and
                        current_time - last_batch_time >= self.batch_timeout):
                    await self.batch_persist_tickets(pending_tickets)
                    pending_tickets.clear()
                    last_batch_time = current_time
            except Exception as e:
                logger.error(f"Error in batch processor: {e}")

        # Process any remaining tickets when shutting down
        if pending_tickets:
            await self.batch_persist_tickets(pending_tickets)


    async def validate_ticket_order(self, order_data: Dict[str, Any], offset: int) -> TicketResultEvent:
        """Validate ticket order and check availability"""
        ticket_id = order_data.get('ticket_id')
        zone_id = order_data.get('zone_id')
        concert_id = order_data.get('concert_id')

        try:
            db = SessionLocal()
            db_session_context.set(db)

            # Check if zone exists and has available seats
            zone = await zone_repository.get(zone_id)

            # Get concert details
            concert = await concert_repository.get(zone.concert_id)

            if offset > zone.zone_capacity:
                return TicketResultEvent(
                    ticket_id=ticket_id,
                    zone_id=zone_id,
                    concert_id=concert_id,
                    status='failed',
                    error='No available seats in this zone'
                )

            # Create ticket data for validation
            ticket_data = {
                'id': ticket_id,
                'zone_id': zone_id,
                'concert_id': concert_id,
                'created_at': datetime.now().isoformat(),
                'updated_at': datetime.now().isoformat(),
                'concert_name': concert.name if concert else None,
                'concert_description': concert.description if concert else None,
                'price': float(zone.price),
                'zone_name': zone.name,
                'zone_description': zone.description
            }

            # Add to queue for batch processing - thread-safe
            ticket_info = {
                'ticket_id': ticket_id,
                'zone_id': zone_id,
                'order_data': order_data,
                'ticket_data': ticket_data,
                'processed_at': time.time()
            }
            await self.ticket_queue.put(ticket_info)

            zone.available_seats -= 1
            update_cache(zone_id, zone)

            logger.info(f"Ticket {ticket_id} validated successfully")
            return TicketResultEvent(
                ticket_id=ticket_id,
                zone_id=zone_id,
                concert_id=zone.concert_id,
                status='success',
                message='Ticket validated and reserved',
                ticket_data=ticket_data
            )

        except Exception as e:
            logger.error(f"Error validating ticket {ticket_id}: {e}")
            return TicketResultEvent(
                ticket_id=ticket_id,
                status='failed',
                error=str(e)
            )
        finally:
            db.close()

    async def batch_persist_tickets(self, tickets_to_persist: List[Dict[str, Any]]):
        """Persist a batch of tickets to database"""
        logger.info(f"batch_persist_tickets called with {len(tickets_to_persist)} tickets")

        if not tickets_to_persist:
            logger.info("No tickets to persist")
            return

        try:
            db = SessionLocal()

            # Batch insert tickets
            zone_ticket_counts = {}
            ticket_objects = []

            for ticket_info in tickets_to_persist:
                ticket_obj = Ticket(
                    id=ticket_info['ticket_id'],
                    zone_id=ticket_info['zone_id']
                )
                ticket_objects.append(ticket_obj)

                zone_id = ticket_info['zone_id']
                zone_ticket_counts[zone_id] = zone_ticket_counts.get(zone_id, 0) + 1

            db.add_all(ticket_objects)

            for zone_id, ticket_count in zone_ticket_counts.items():
                zone = db.query(Zone).filter(Zone.id == zone_id).first()
                if zone:
                    zone.available_seats -= ticket_count
                    logger.info(f"Decreased {ticket_count} seats for zone {zone_id}")

            db.commit()
            logger.info(f"Batch persisted {len(ticket_objects)} tickets to database")

        except Exception as e:
            logger.error(f"Error batch persisting tickets: {e}")
            # Re-queue failed tickets for retry
            for ticket_info in tickets_to_persist:
                await self.ticket_queue.put(ticket_info)
        finally:
            db.close()

    async def process_messages(self):
        """Process incoming ticket order messages"""
        if not self.consumer:
            await self.connect()
            if not self.consumer:
                logger.error("Consumer not available")
                return

        logger.info("Starting ticket processor...")
        self.running = True

        # Start the background batch processor
        self.batch_task = asyncio.create_task(self.start_batch_processor())

        try:
            async for message in self.consumer:
                try:
                    order_data = message.value
                    logger.info(f"Processing ticket order: {order_data.get('ticket_id')} with offset {message.offset}")

                    # Validate ticket order
                    result = await self.validate_ticket_order(order_data, message.offset)

                    # Produce result to ticket-events topic
                    await ticket_producer.produce_ticket_result(result)

                except Exception as e:
                    logger.error(f"Error processing message: {e}")

        except Exception as e:
            logger.error(f"Error in message processing: {e}")
        finally:
            await self.cleanup()

    async def cleanup(self):
        """Clean up resources"""
        self.running = False

        if self.consumer:
            await self.consumer.stop()
            logger.info("Consumer closed")

        # Wait for queue to be processed
        if self.batch_task:
            await self.ticket_queue.join()  # Wait for all items to be processed
            self.batch_task.cancel()
            try:
                await self.batch_task
            except asyncio.CancelledError:
                pass


# Global processor instance
ticket_processor = TicketProcessor()


async def start_ticket_processor():
    """Start the ticket processor service"""
    await ticket_processor.process_messages()


if __name__ == "__main__":
    # Run the processor as standalone service
    asyncio.run(start_ticket_processor())