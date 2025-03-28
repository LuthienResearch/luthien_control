"""Tests for the database logger."""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from luthien_control.logging.models import Base, Comm
from luthien_control.logging.db_logger import DBLogger

@pytest.fixture(scope="function")
def engine():
    """Create a test database engine."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return engine

@pytest.fixture(scope="function")
def session(engine):
    """Create a new database session for testing."""
    with Session(engine) as session:
        yield session
        session.rollback()

@pytest.fixture
def logger(session):
    """Create a DBLogger instance for testing."""
    return DBLogger(session)

def test_log_comm(logger, session):
    """Test logging a single communication."""
    comm = logger.log_comm(
        source="client",
        destination="proxy",
        comm_type="REQUEST",
        content={"body": "test"},
        endpoint="/test",
        arguments={"param": "value"}
    )

    # Verify the comm was created
    assert comm.id is not None
    assert comm.source == "client"
    assert comm.destination == "proxy"
    assert comm.type == "REQUEST"
    assert comm.content == {"body": "test"}
    assert comm.endpoint == "/test"
    assert comm.arguments == {"param": "value"}

    # Verify it's in the database
    db_comm = session.query(Comm).filter_by(id=comm.id).first()
    assert db_comm is not None
    assert db_comm.content == {"body": "test"}

def test_add_relationship(logger, session):
    """Test creating relationships between communications."""
    # Create two comms
    req = logger.log_comm(
        source="client",
        destination="proxy",
        comm_type="REQUEST",
        content={"original": "request"}
    )
    
    resp = logger.log_comm(
        source="proxy",
        destination="client",
        comm_type="RESPONSE",
        content={"response": "data"}
    )

    # Create relationship
    rel = logger.add_relationship(
        req,
        resp,
        "request_response",
        meta_info={"latency_ms": 150}
    )

    assert rel.from_comm_id == req.id
    assert rel.to_comm_id == resp.id
    assert rel.relationship_type == "request_response"
    assert rel.meta_info == {"latency_ms": 150}

def test_get_related_comms(logger):
    """Test retrieving related communications."""
    # Create a chain of communications
    client_req = logger.log_comm(
        source="client",
        destination="proxy",
        comm_type="REQUEST"
    )
    
    proxy_req = logger.log_comm(
        source="proxy",
        destination="api",
        comm_type="REQUEST"
    )
    
    api_resp = logger.log_comm(
        source="api",
        destination="proxy",
        comm_type="RESPONSE"
    )

    # Create relationships
    logger.add_relationship(client_req, proxy_req, "transformed")
    logger.add_relationship(proxy_req, api_resp, "request_response")

    # Test getting all related comms
    related = logger.get_related_comms(proxy_req)
    assert len(related) == 2
    assert client_req in related  # incoming relationship
    assert api_resp in related    # outgoing relationship

    # Test filtering by relationship type
    transformed = logger.get_related_comms(proxy_req, relationship_type="transformed")
    assert len(transformed) == 1
    assert client_req in transformed

def test_complex_relationship_chain(logger):
    """Test a more complex chain of relationships."""
    # Create a full request/response cycle
    client_req = logger.log_comm(source="client", destination="proxy", comm_type="REQUEST")
    proxy_req = logger.log_comm(source="proxy", destination="api", comm_type="REQUEST")
    api_resp = logger.log_comm(source="api", destination="proxy", comm_type="RESPONSE")
    proxy_resp = logger.log_comm(source="proxy", destination="client", comm_type="RESPONSE")

    # Create the relationship chain
    logger.add_relationship(client_req, proxy_req, "transformed")
    logger.add_relationship(proxy_req, api_resp, "request_response")
    logger.add_relationship(api_resp, proxy_resp, "transformed")

    # Test navigation from client request
    related_to_client = logger.get_related_comms(client_req)
    assert len(related_to_client) == 1
    assert proxy_req in related_to_client

    # Test navigation from proxy request
    related_to_proxy = logger.get_related_comms(proxy_req)
    assert len(related_to_proxy) == 2
    assert client_req in related_to_proxy
    assert api_resp in related_to_proxy

    # Test navigation from API response
    related_to_api = logger.get_related_comms(api_resp)
    assert len(related_to_api) == 2
    assert proxy_req in related_to_api
    assert proxy_resp in related_to_api 