# Error Handling Strategy

This document outlines the standardized approach to error handling in the Luthien Control project.

## Core Principles

1. **Fail Fast and Explicitly**: Code should fail loudly and obviously when encountering errors rather than silently continuing with invalid state.
2. **Consistent Return Types**: Functions should have consistent return behavior - either always return a value/Optional or always raise exceptions.
3. **Informative Error Messages**: Error messages should provide clear context about what went wrong and how to fix it.
4. **Proper Error Hierarchy**: Errors should inherit from appropriate base classes to enable catch-by-category.
5. **Comprehensive Logging**: All errors should be logged with appropriate severity and context.

## When to Use Exceptions vs. Optional Returns

### Use Exceptions When:

- **Configuration Errors**: Missing or invalid configuration that prevents normal operation
- **Authentication/Authorization Failures**: Security-related failures
- **Database Connection Issues**: Connection failures, transaction errors
- **External Service Failures**: Network errors, timeouts, unexpected responses
- **Data Integrity Violations**: Constraint violations, invalid data formats
- **Programming Errors**: Invalid arguments, state violations, assertion failures

### Use Optional Returns (None) When:

- **Resource Not Found**: When looking up an entity by ID/name and it doesn't exist
- **Empty Collections**: When querying for collections that might be empty
- **Optional Parameters**: When a parameter is truly optional and None is a valid value

## Error Hierarchy

The project uses two main error hierarchies:

1. **ControlPolicyError**: Base class for all policy-related errors
2. **LuthienDBException**: Base class for all database-related errors

### New Database Error Types

We are extending the database error hierarchy with:

- **LuthienDBOperationError**: For general database operation failures
  - **LuthienDBQueryError**: For errors during query execution
  - **LuthienDBTransactionError**: For transaction-related errors
  - **LuthienDBIntegrityError**: For data integrity violations (wraps SQLAlchemy's IntegrityError)

## Error Handling in CRUD Operations

### Standard Pattern for CRUD Operations

```python
async def create_entity(session: AsyncSession, entity: Entity) -> Entity:
    """Create a new entity in the database.
    
    Args:
        session: The database session
        entity: The entity to create
        
    Returns:
        The created entity with updated ID
        
    Raises:
        LuthienDBIntegrityError: If a constraint violation occurs
        LuthienDBTransactionError: If the transaction fails
        LuthienDBOperationError: For other database errors
    """
    try:
        session.add(entity)
        await session.commit()
        await session.refresh(entity)
        logger.info(f"Successfully created entity with ID: {entity.id}")
        return entity
    except IntegrityError as ie:
        await session.rollback()
        logger.error(f"Integrity error creating entity: {ie}")
        raise LuthienDBIntegrityError(f"Could not create entity due to constraint violation: {ie}") from ie
    except SQLAlchemyError as sqla_err:
        await session.rollback()
        logger.error(f"SQLAlchemy error creating entity: {sqla_err}")
        raise LuthienDBTransactionError(f"Database transaction failed while creating entity: {sqla_err}") from sqla_err
    except Exception as e:
        await session.rollback()
        logger.error(f"Unexpected error creating entity: {e}")
        raise LuthienDBOperationError(f"Unexpected error during entity creation: {e}") from e
```

### Standard Pattern for Lookup Operations

```python
async def get_entity_by_id(session: AsyncSession, entity_id: int) -> Optional[Entity]:
    """Get an entity by its ID.
    
    Args:
        session: The database session
        entity_id: The ID of the entity to retrieve
        
    Returns:
        The entity if found, None otherwise
        
    Raises:
        LuthienDBQueryError: If the query execution fails
    """
    try:
        stmt = select(Entity).where(Entity.id == entity_id)
        result = await session.execute(stmt)
        entity = result.scalar_one_or_none()
        return entity
    except SQLAlchemyError as sqla_err:
        logger.error(f"SQLAlchemy error fetching entity by ID {entity_id}: {sqla_err}")
        raise LuthienDBQueryError(f"Database query failed while fetching entity with ID {entity_id}: {sqla_err}") from sqla_err
    except Exception as e:
        logger.error(f"Unexpected error fetching entity by ID {entity_id}: {e}")
        raise LuthienDBOperationError(f"Unexpected error during entity lookup: {e}") from e
```

## Error Handling in API Endpoints

API endpoints should:

1. Catch specific exceptions and translate them to appropriate HTTP status codes
2. Log errors with request context
3. Return standardized error responses with clear messages
4. Not expose internal implementation details or stack traces

## Logging Best Practices

1. Use appropriate log levels:
   - ERROR: For errors that require attention
   - WARNING: For concerning but non-critical issues
   - INFO: For normal operations
   - DEBUG: For detailed troubleshooting

2. Include context in log messages:
   - Transaction/request IDs
   - User/client identifiers (when available)
   - Relevant entity IDs
   - Operation being performed

3. Avoid logging sensitive information:
   - API keys
   - Passwords
   - Personal data
   - Full request/response bodies

## Implementation Checklist

- [ ] Update exceptions.py with new error types
- [ ] Standardize client_api_key_crud.py
- [ ] Standardize control_policy_crud.py
- [ ] Update other CRUD operations
- [ ] Update tests to match new error handling
- [ ] Update documentation
