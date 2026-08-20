from functools import lru_cache

from redis import Redis
from rq import Queue

from app.config import get_settings

RESEARCH_QUEUE_NAME = "helixmind-research"


@lru_cache
def get_redis_connection() -> Redis:
    return Redis.from_url(get_settings().redis_url, decode_responses=False)


def get_research_queue() -> Queue:
    return Queue(RESEARCH_QUEUE_NAME, connection=get_redis_connection(), default_timeout=900)
