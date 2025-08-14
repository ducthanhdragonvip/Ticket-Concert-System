import logging
from src.utils.database import Base, engine

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def init_database():
    """Initialize the database by creating all tables."""
    try:
        logger.info("Starting database initialization...")

        # Create all tables defined in the models
        Base.metadata.create_all(bind=engine)

        logger.info("Database tables created successfully!")

    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise


if __name__ == "__main__":
    init_database()