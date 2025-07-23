import os
from dotenv import load_dotenv

load_dotenv()

class Settings():
    DATABASE_URL: str =  os.getenv('DATABASE_URL')
    REDIS_HOST: str = os.getenv('REDIS_HOST')
    REDIS_PORT: int = int(os.getenv('REDIS_PORT'))
    KAFKA_BOOTSTRAP_SERVERS: str = os.getenv('KAFKA_BOOTSTRAP_SERVERS')

settings = Settings()

