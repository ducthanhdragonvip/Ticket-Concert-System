from sqlalchemy.orm import Session

from src.kafka.consumer import ticket_result_consumer
from src.utils.kafka_config import TicketOrderEvent
from src.utils.database import db_session_context
from src.entities.ticket import Ticket
from src.entities.zone import Zone
from src.dto.ticket import TicketCreate, TicketUpdate, TicketDetail
from src.repositories.base import BaseRepository
from src.repositories.zone_repository import zone_repository
from src.utils.cache import cache_data, update_cache
from src.kafka.producer import ticket_producer
from uuid import uuid4
import logging

logger = logging.getLogger(__name__)


class TicketRepository(BaseRepository[Ticket, TicketCreate, TicketUpdate]):
    def __init__(self):
        super().__init__(Ticket)

    # @cache_data(expire_time=3600, use_result_id=True)
    async def create(self,obj_in: TicketCreate) -> TicketDetail:
        # db = db_session_context.get()
        # First check if zone exists and has available seats
        zone = await zone_repository.get(obj_in.zone_id)

        if not zone:
            raise ValueError("Zone not found")

        if str(obj_in.concert_id) not in str(obj_in.zone_id):
            raise ValueError("Zone does not belong to the specified concert")

        if zone.available_seats <= 0:
            raise ValueError("No available seats in this zone")
        #
        # concert = await concert_repository.get(zone.concert_id)

        # test Kafka producer
        ticket_id = str(uuid4())
        ticket_order = TicketOrderEvent(
            ticket_id=ticket_id,
            zone_id=obj_in.zone_id,
            concert_id=obj_in.concert_id
        )

        success = await ticket_producer.produce_ticket_order(ticket_order)
        if not success:
            raise RuntimeError("Failed to submit ticket order to processing queue")

        logger.info(f"Ticket order {ticket_id} submitted to Kafka")

        result = await ticket_result_consumer.wait_for_ticket_result(ticket_id, timeout=30)

        if not result:
            raise TimeoutError("Ticket processing timeout. Please try again or check your order status.")

        if result['status'] == 'failed':
            error_message = result.get('error', 'Unknown error occurred')
            if 'available seats' in error_message.lower():
                raise ValueError(error_message)
            elif 'not found' in error_message.lower():
                raise ValueError(error_message)
            else:
                raise RuntimeError(error_message)

        ticket_data = result.get('ticket_data', {})
        return TicketDetail(**ticket_data)

        # Create the ticket
        # db_obj = Ticket(
        #     id=str(ticket_id),
        #     zone_id=obj_in.zone_id,
        #     # status=obj_in.status
        # )
        # db.add(db_obj)
        #
        # # Decrement available seats
        # zone = db.merge(zone)
        # zone.available_seats -= 1
        #
        # try:
        #     db.commit()
        #     db.refresh(db_obj)
        #     db.refresh(zone)
        #
        #     update_cache(obj_in.zone_id, zone)
        #     return TicketDetail(
        #         id=db_obj.id,
        #         zone_id=db_obj.zone_id,
        #         # status=db_obj.status,
        #         created_at=db_obj.created_at,
        #         updated_at=db_obj.updated_at,
        #         concert_name=concert.name if concert else None,
        #         concert_description=concert.description if concert else None,
        #         price=zone.price if zone else None,
        #         zone_name=zone.name if zone else None,
        #         zone_description=zone.description if zone else None
        #     )
        # except Exception as e:
        #     db.rollback()
        #     raise HTTPException(status_code=500, detail=str(e))

    @cache_data(expire_time=3600)
    async def get_with_details(self, ticket_id: str) -> TicketDetail | None:
        db = db_session_context.get()
        from src.repositories.zone_repository import zone_repository
        from src.repositories.concert_repository import concert_repository

        ticket = await self.get(ticket_id)
        if not ticket:
            return None

        zone = await zone_repository.get(ticket.zone_id)
        concert = None
        if zone:
            concert = await concert_repository.get(zone.concert_id)

        # Create TicketDetail with extracted information
        return TicketDetail(
            id=ticket.id,
            zone_id=ticket.zone_id,
            concert_id=zone.concert_id,
            # status=ticket.status,
            created_at=ticket.created_at,
            updated_at=ticket.updated_at,
            concert_name=concert.name if concert else None,
            concert_description=concert.description if concert else None,
            price=zone.price if zone else None,
            zone_name=zone.name if zone else None,
            zone_description=zone.description if zone else None
        )

    async def get_by_concert(self,concert_id: str) -> list[Ticket]:
        db = db_session_context.get()
        tickets = db.query(self.model).join(Zone).filter(Zone.concert_id == concert_id).all()
        result = []
        for ticket in tickets:
            ticket_detail = await self.get_with_details(ticket.id)
            if ticket_detail:
                result.append(ticket_detail)
        return result

    async def get_by_zone(self, zone_id: str) -> list[Ticket]:
        db = db_session_context.get()
        tickets = db.query(self.model).filter(self.model.zone_id == zone_id).all()

        result = []
        for ticket in tickets:
            ticket_detail = await self.get_with_details(ticket.id)
            if ticket_detail:
                result.append(ticket_detail)

        return result

ticket_repository = TicketRepository()