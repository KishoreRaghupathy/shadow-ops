import os
from contextlib import contextmanager
from neo4j import GraphDatabase, basic_auth
from config.settings import settings

# Initialize Neo4j driver using settings
_driver = None

def _init_driver():
    global _driver
    if _driver is None:
        auth = basic_auth(settings.NEO4J_USER, settings.NEO4J_PASSWORD)
        _driver = GraphDatabase.driver(settings.NEO4J_URI, auth=auth)
        settings.logger.info(f"Neo4j driver initialized for {settings.NEO4J_URI}")
    return _driver

@contextmanager
def get_session():
    """Yield a Neo4j session and ensure it is closed after use."""
    driver = _init_driver()
    session = driver.session()
    try:
        yield session
    finally:
        session.close()

def run_query(query: str, parameters: dict | None = None):
    """Convenient helper to run a Cypher query and return the result list.
    Parameters:
        query: Cypher query string.
        parameters: Optional dict of query parameters.
    Returns:
        List of records (as dicts) from the query.
    """
    with get_session() as session:
        result = session.run(query, parameters or {})
        return [record.data() for record in result]
