from fastapi import APIRouter
from src.api.ticket_system import api_tickets, api_concerts, api_zones, api_venues

router = APIRouter()

router.include_router(api_venues.router)
router.include_router(api_concerts.router)
router.include_router(api_zones.router)
router.include_router(api_tickets.router)