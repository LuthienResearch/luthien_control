"""
Database models for the communications logging system.
"""
from datetime import datetime
import uuid
from typing import Dict, Any, Optional

from sqlalchemy import Column, DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship, declarative_base

Base = declarative_base()

class Comm(Base):
    """A single communication unit representing any type of message."""
    __tablename__ = "comms"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source = Column(Text, nullable=False)
    destination = Column(Text, nullable=False)
    type = Column(Enum("REQUEST", "RESPONSE", name="comm_type"), nullable=False)
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow)
    content = Column(JSONB)
    endpoint = Column(Text)
    arguments = Column(JSONB)
    trigger = Column(JSONB)  # For control-server originated comms

    # Relationships
    outgoing_relationships = relationship(
        "CommRelationship",
        foreign_keys="CommRelationship.from_comm_id",
        back_populates="from_comm"
    )
    incoming_relationships = relationship(
        "CommRelationship",
        foreign_keys="CommRelationship.to_comm_id",
        back_populates="to_comm"
    )

class CommRelationship(Base):
    """Represents a relationship between two communications."""
    __tablename__ = "comm_relationships"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    from_comm_id = Column(UUID(as_uuid=True), ForeignKey("comms.id"), nullable=False)
    to_comm_id = Column(UUID(as_uuid=True), ForeignKey("comms.id"), nullable=False)
    relationship_type = Column(Text, nullable=False)
    meta_info = Column(JSONB, nullable=False, default=dict)

    # Relationships
    from_comm = relationship(
        "Comm",
        foreign_keys=[from_comm_id],
        back_populates="outgoing_relationships"
    )
    to_comm = relationship(
        "Comm",
        foreign_keys=[to_comm_id],
        back_populates="incoming_relationships"
    ) 