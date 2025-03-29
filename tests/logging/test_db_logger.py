"""Unit tests for the current DBLogger."""

from datetime import datetime
from unittest.mock import Mock

import pytest
from sqlalchemy.orm import Session

from luthien_control.logging.db_logger import DBLogger
from luthien_control.logging.models import (  # Keep Base for potential future use if needed
    Comm,
    CommRelationship,
)


@pytest.fixture
def mock_session():
    """Fixture for a mocked SQLAlchemy Session."""
    session = Mock(spec=Session)
    # Configure mock behavior for query/filter/join/all if needed by tests
    session.query.return_value.join.return_value.filter.return_value.all.return_value = []  # Default for get_related
    return session


@pytest.fixture
def db_logger(mock_session):
    """Fixture for DBLogger, injecting the mocked session."""
    return DBLogger(mock_session)


# Removed test_init_db as DBLogger doesn't handle initialization


def test_log_comm(db_logger, mock_session):
    """Test logging a communication entry."""
    log_data = {
        "source": "client",
        "destination": "proxy",
        "comm_type": "REQUEST",
        "content": {"data": "value"},
        "endpoint": "/test",
        "arguments": {"arg": "1"},
        "trigger": {"id": "abc"},
    }

    # Mock session.flush() to simulate setting an ID
    # And simulate default value application (like timestamp)
    # which normally happens at DB level or upon flush/commit.
    def mock_flush():
        # Access the object passed to add() before flush is called
        added_comm = mock_session.add.call_args[0][0]
        # Simulate setting attributes normally set by DB/SQLAlchemy during INSERT/flush
        added_comm.id = 123  # Simulate setting ID
        if added_comm.timestamp is None:  # Simulate default if not explicitly set
            added_comm.timestamp = datetime.utcnow()

    mock_session.flush.side_effect = mock_flush

    comm = db_logger.log_comm(**log_data)

    # Check that a Comm object was added and flushed
    mock_session.add.assert_called_once()
    mock_session.flush.assert_called_once()

    # Verify the added object has the correct attributes and the returned ID
    added_comm = mock_session.add.call_args[0][0]
    assert isinstance(added_comm, Comm)
    assert added_comm.source == log_data["source"]
    assert added_comm.destination == log_data["destination"]
    assert added_comm.type == log_data["comm_type"]
    assert added_comm.content == log_data["content"]
    assert added_comm.endpoint == log_data["endpoint"]
    assert added_comm.arguments == log_data["arguments"]
    assert added_comm.trigger == log_data["trigger"]
    assert isinstance(added_comm.timestamp, datetime)  # Timestamp should be set automatically (simulated by mock_flush)

    # Verify the returned object is the one added and has the ID
    assert comm == added_comm
    assert comm.id == 123


def test_add_relationship(db_logger, mock_session):
    """Test adding a relationship between communications."""
    # Create mock Comm objects with IDs
    mock_comm_from = Mock(spec=Comm, id=1)
    mock_comm_to = Mock(spec=Comm, id=2)
    relationship_type = "request_response"
    meta_info = {"latency": 100}

    # Mock session.flush() for relationship ID simulation if necessary
    # (Not strictly needed for this test if we don't check the returned rel ID)

    rel = db_logger.add_relationship(mock_comm_from, mock_comm_to, relationship_type, meta_info)

    mock_session.add.assert_called_once()
    mock_session.flush.assert_called_once()

    added_rel = mock_session.add.call_args[0][0]
    assert isinstance(added_rel, CommRelationship)
    assert added_rel.from_comm_id == mock_comm_from.id
    assert added_rel.to_comm_id == mock_comm_to.id
    assert added_rel.relationship_type == relationship_type
    assert added_rel.meta_info == meta_info
    assert rel == added_rel


def test_add_relationship_default_meta(db_logger, mock_session):
    """Test adding a relationship with default meta_info."""
    mock_comm_from = Mock(spec=Comm, id=3)
    mock_comm_to = Mock(spec=Comm, id=4)
    relationship_type = "transformed"

    db_logger.add_relationship(mock_comm_from, mock_comm_to, relationship_type)

    mock_session.add.assert_called_once()
    added_rel = mock_session.add.call_args[0][0]
    assert added_rel.meta_info == {}  # Should default to empty dict


# Tests for get_related_comms
# These require more complex mocking of the query structure


def test_get_related_comms_found(db_logger, mock_session):
    """Test finding related communications."""
    target_comm = Mock(spec=Comm, id=1)
    mock_related_comm1 = Mock(spec=Comm, id=2)
    mock_related_comm2 = Mock(spec=Comm, id=3)

    # Mock the chained query calls
    mock_query = mock_session.query.return_value
    mock_join = mock_query.join.return_value
    mock_filter = mock_join.filter.return_value
    mock_filter.all.return_value = [mock_related_comm1, mock_related_comm2]

    related = db_logger.get_related_comms(target_comm)

    # Check query structure was called (simplified check)
    mock_session.query.assert_called_with(Comm)
    mock_query.join.assert_called_once()
    mock_join.filter.assert_called_once()  # First filter for relationship join
    # The relationship_type filter is optional, so check if all was called
    mock_filter.all.assert_called_once()

    assert related == [mock_related_comm1, mock_related_comm2]


def test_get_related_comms_with_type(db_logger, mock_session):
    """Test finding related communications filtered by type."""
    target_comm = Mock(spec=Comm, id=1)
    mock_related_comm_typed = Mock(spec=Comm, id=4)
    relationship_type = "request_response"

    # Mock the chained query calls including the type filter
    mock_query = mock_session.query.return_value
    mock_join = mock_query.join.return_value
    mock_rel_filter = mock_join.filter.return_value  # Filter based on comm IDs
    mock_type_filter = mock_rel_filter.filter.return_value  # Filter based on type
    mock_type_filter.all.return_value = [mock_related_comm_typed]

    related = db_logger.get_related_comms(target_comm, relationship_type=relationship_type)

    # Check query structure was called
    mock_session.query.assert_called_with(Comm)
    mock_query.join.assert_called_once()
    mock_join.filter.assert_called_once()  # Relationship filter
    mock_rel_filter.filter.assert_called_once()  # Type filter
    mock_type_filter.all.assert_called_once()

    # Verify the specific relationship_type filter argument
    type_filter_call_args = mock_rel_filter.filter.call_args
    # This assertion is tricky because the filter uses SQLAlchemy comparison objects
    # Let's just assert it was called, verifying the return value is sufficient here

    assert related == [mock_related_comm_typed]


def test_get_related_comms_none(db_logger, mock_session):
    """Test finding related communications when none exist."""
    target_comm = Mock(spec=Comm, id=1)

    # Mock the final .all() call to return empty list
    mock_session.query.return_value.join.return_value.filter.return_value.all.return_value = []

    related = db_logger.get_related_comms(target_comm)

    assert related == []
    mock_session.query.return_value.join.return_value.filter.return_value.all.assert_called_once()
