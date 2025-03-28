"""
Database logger for API communications.
"""
from typing import Any, Dict, Optional
from sqlalchemy.orm import Session

from .models import Comm, CommRelationship

class DBLogger:
    """Logger for API communications that stores data in a database."""
    
    def __init__(self, session: Session):
        """Initialize logger with database session."""
        self.session = session
    
    def log_comm(
        self,
        source: str,
        destination: str,
        comm_type: str,
        content: Optional[Dict] = None,
        endpoint: Optional[str] = None,
        arguments: Optional[Dict] = None,
        trigger: Optional[Dict] = None
    ) -> Comm:
        """Log a communication."""
        comm = Comm(
            source=source,
            destination=destination,
            type=comm_type,
            content=content,
            endpoint=endpoint,
            arguments=arguments,
            trigger=trigger
        )
        
        self.session.add(comm)
        self.session.flush()  # To get the ID
        return comm
    
    def add_relationship(
        self,
        from_comm: Comm,
        to_comm: Comm,
        relationship_type: str,
        meta_info: Optional[Dict] = None
    ) -> CommRelationship:
        """Create a relationship between two communications."""
        rel = CommRelationship(
            from_comm_id=from_comm.id,
            to_comm_id=to_comm.id,
            relationship_type=relationship_type,
            meta_info=meta_info or {}
        )
        
        self.session.add(rel)
        self.session.flush()
        return rel
    
    def get_related_comms(
        self,
        comm: Comm,
        relationship_type: Optional[str] = None,
    ) -> list[Comm]:
        """Get all communications related to the given one."""
        # Get outgoing relationships
        query = self.session.query(Comm).join(
            CommRelationship,
            (CommRelationship.to_comm_id == Comm.id) |
            (CommRelationship.from_comm_id == Comm.id)
        ).filter(
            ((CommRelationship.from_comm_id == comm.id) |
            (CommRelationship.to_comm_id == comm.id)) &
            (Comm.id != comm.id)  # Exclude the original communication
        )
        
        if relationship_type:
            query = query.filter(CommRelationship.relationship_type == relationship_type)
            
        return query.all() 