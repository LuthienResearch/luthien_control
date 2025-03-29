"""Tests for database models."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from luthien_control.logging.models import Base, Comm, CommRelationship


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


def test_create_comm(session):
    """Test creating a communication record."""
    comm = Comm(
        source="client",
        destination="proxy",
        type="REQUEST",
        content={"body": "test"},
        endpoint="/test",
        arguments={"param": "value"},
    )
    session.add(comm)
    session.flush()

    assert comm.id is not None
    assert comm.source == "client"
    assert comm.destination == "proxy"
    assert comm.type == "REQUEST"
    assert comm.content == {"body": "test"}
    assert comm.endpoint == "/test"
    assert comm.arguments == {"param": "value"}
    assert comm.trigger is None


def test_create_relationship(session):
    """Test creating a relationship between communications."""
    comm1 = Comm(source="client", destination="proxy", type="REQUEST")
    comm2 = Comm(source="proxy", destination="api", type="REQUEST")
    session.add_all([comm1, comm2])
    session.flush()

    rel = CommRelationship(
        from_comm_id=comm1.id, to_comm_id=comm2.id, relationship_type="transformed", meta_info={"changes": ["headers"]}
    )
    session.add(rel)
    session.flush()

    assert rel.id is not None
    assert rel.from_comm_id == comm1.id
    assert rel.to_comm_id == comm2.id
    assert rel.relationship_type == "transformed"
    assert rel.meta_info == {"changes": ["headers"]}


def test_relationship_navigation(session):
    """Test navigating relationships between communications."""
    # Create a chain: client -> proxy -> api
    client_req = Comm(source="client", destination="proxy", type="REQUEST")
    proxy_req = Comm(source="proxy", destination="api", type="REQUEST")
    api_resp = Comm(source="api", destination="proxy", type="RESPONSE")
    proxy_resp = Comm(source="proxy", destination="client", type="RESPONSE")

    session.add_all([client_req, proxy_req, api_resp, proxy_resp])
    session.flush()

    # Create relationships
    rels = [
        CommRelationship(from_comm_id=client_req.id, to_comm_id=proxy_req.id, relationship_type="transformed"),
        CommRelationship(from_comm_id=proxy_req.id, to_comm_id=api_resp.id, relationship_type="request_response"),
        CommRelationship(from_comm_id=api_resp.id, to_comm_id=proxy_resp.id, relationship_type="transformed"),
    ]
    session.add_all(rels)
    session.flush()

    # Test navigation
    assert len(client_req.outgoing_relationships) == 1
    assert len(client_req.incoming_relationships) == 0
    assert client_req.outgoing_relationships[0].to_comm == proxy_req

    assert len(proxy_req.outgoing_relationships) == 1
    assert len(proxy_req.incoming_relationships) == 1
    assert proxy_req.outgoing_relationships[0].to_comm == api_resp
    assert proxy_req.incoming_relationships[0].from_comm == client_req

    assert len(api_resp.outgoing_relationships) == 1
    assert len(api_resp.incoming_relationships) == 1
    assert api_resp.outgoing_relationships[0].to_comm == proxy_resp
    assert api_resp.incoming_relationships[0].from_comm == proxy_req

    assert len(proxy_resp.outgoing_relationships) == 0
    assert len(proxy_resp.incoming_relationships) == 1
    assert proxy_resp.incoming_relationships[0].from_comm == api_resp
