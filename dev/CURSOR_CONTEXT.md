# Current Working Context

## Implementation Phase
- Planning phase for request/response exploration system
- Focus on data model and storage design

## Working State
- Designing new feature for exploring proxy communications
- Current design decisions:
  - Base unit: "Comm" for tracking requests/responses
  - PostgreSQL database
  - Flexible relationship modeling
  - Full semantic data storage
  - Support for 1k-100k records initially

## Current Blockers
- Need to research standard terminology for source/destination fields
- Need to validate query performance assumptions
- Need to design basic UI requirements

## Next Steps
1. Research and finalize source/destination terminology
2. Design schema indexes
3. Plan basic query patterns
4. Design logging/querying API
5. Plan minimal UI requirements

## Data Model (Current Draft)
### Comm Table
- id: uuid
- source: text
- destination: text
- type: enum (request, response)
- timestamp: timestamp
- content: jsonb
- endpoint: text
- arguments: jsonb
- trigger: jsonb

### CommRelationship Table
- id: uuid
- from_comm_id: uuid
- to_comm_id: uuid
- relationship_type: text
- metadata: jsonb 