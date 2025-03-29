"""
Database models for the communications logging system.
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Column, DateTime, Enum, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, relationship

# Create a Base class using DeclarativeBase for Mypy compatibility
class Base(DeclarativeBase):
    pass
    # Optional: Define common types or metadata here
    # type_annotation_map = {
    #     dict[str, Any]: JSON
    # }


class Comm(Base):
    """A single communication unit representing any type of message."""

    __tablename__ = "comms"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source = Column(Text, nullable=False)
    destination = Column(Text, nullable=False)
    type = Column(Enum("REQUEST", "RESPONSE", name="comm_type"), nullable=False)
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow)
    content = Column(JSON)
    endpoint = Column(Text)
    arguments = Column(JSON)
    trigger = Column(JSON)  # For control-server originated comms

    # Relationships
    outgoing_relationships = relationship(
        "CommRelationship", foreign_keys="CommRelationship.from_comm_id", back_populates="from_comm"
    )
    incoming_relationships = relationship(
        "CommRelationship", foreign_keys="CommRelationship.to_comm_id", back_populates="to_comm"
    )


class CommRelationship(Base):
    """Represents a relationship between two communications."""

    __tablename__ = "comm_relationships"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    from_comm_id = Column(UUID(as_uuid=True), ForeignKey("comms.id"), nullable=False)
    to_comm_id = Column(UUID(as_uuid=True), ForeignKey("comms.id"), nullable=False)
    relationship_type = Column(Text, nullable=False)
    meta_info = Column(JSON, nullable=False, default=dict)

    # Relationships
    from_comm = relationship("Comm", foreign_keys=[from_comm_id], back_populates="outgoing_relationships")
    to_comm = relationship("Comm", foreign_keys=[to_comm_id], back_populates="incoming_relationships")
