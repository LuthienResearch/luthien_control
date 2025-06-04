import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from luthien_control.core.dependencies import get_db_session
from luthien_control.db.exceptions import LuthienDBOperationError, LuthienDBQueryError
from luthien_control.db.luthien_log_crud import (
    count_logs,
    get_log_by_id,
    get_unique_datatypes,
    get_unique_transaction_ids,
    list_logs,
)

logger = logging.getLogger(__name__)

router = APIRouter()
templates = Jinja2Templates(directory="luthien_control/logs/templates")


@router.get("/admin/logs", response_class=HTMLResponse)
async def logs_ui(request: Request):
    """Serve the logs exploration UI."""
    return templates.TemplateResponse("logs.html", {"request": request})


@router.get("/admin/logs-api/logs")
async def get_logs(
    session: AsyncSession = Depends(get_db_session),
    transaction_id: Optional[str] = Query(None, description="Filter by transaction ID"),
    datatype: Optional[str] = Query(None, description="Filter by datatype"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of logs to return"),
    offset: int = Query(0, ge=0, description="Number of logs to skip"),
    start_datetime: Optional[str] = Query(None, description="Start datetime (ISO format)"),
    end_datetime: Optional[str] = Query(None, description="End datetime (ISO format)"),
) -> Dict[str, Any]:
    """Get logs with optional filtering and pagination.

    Returns:
        Dictionary containing logs, pagination info, and metadata
    """
    try:
        # Parse datetime strings if provided
        start_dt = None
        end_dt = None
        if start_datetime:
            try:
                start_dt = datetime.fromisoformat(start_datetime.replace("Z", "+00:00"))
            except ValueError as e:
                raise HTTPException(status_code=400, detail=f"Invalid start_datetime format: {e}")

        if end_datetime:
            try:
                end_dt = datetime.fromisoformat(end_datetime.replace("Z", "+00:00"))
            except ValueError as e:
                raise HTTPException(status_code=400, detail=f"Invalid end_datetime format: {e}")

        # Get logs and total count
        logs = await list_logs(
            session=session,
            transaction_id=transaction_id,
            datatype=datatype,
            limit=limit,
            offset=offset,
            start_datetime=start_dt,
            end_datetime=end_dt,
        )

        total_count = await count_logs(
            session=session,
            transaction_id=transaction_id,
            datatype=datatype,
            start_datetime=start_dt,
            end_datetime=end_dt,
        )

        # Convert logs to dict format for JSON response
        logs_data = []
        for log in logs:
            log_dict = {
                "id": log.id,
                "transaction_id": log.transaction_id,
                "datetime": log.datetime.isoformat() if log.datetime else None,
                "datatype": log.datatype,
                "data": log.data,
                "notes": log.notes,
            }
            logs_data.append(log_dict)

        return {
            "logs": logs_data,
            "pagination": {
                "limit": limit,
                "offset": offset,
                "total": total_count,
                "has_next": offset + limit < total_count,
                "has_prev": offset > 0,
            },
            "filters": {
                "transaction_id": transaction_id,
                "datatype": datatype,
                "start_datetime": start_datetime,
                "end_datetime": end_datetime,
            },
        }

    except HTTPException:
        # Re-raise HTTPExceptions (like 400 Bad Request) without modification
        raise
    except (LuthienDBQueryError, LuthienDBOperationError) as db_err:
        logger.error(f"Database error getting logs: {db_err}")
        raise HTTPException(status_code=500, detail="Failed to retrieve logs from database")
    except Exception as e:
        logger.error(f"Unexpected error getting logs: {e}")
        raise HTTPException(status_code=500, detail="An unexpected error occurred")


@router.get("/admin/logs-api/logs/{log_id}")
async def get_log(
    log_id: int,
    session: AsyncSession = Depends(get_db_session),
) -> Dict[str, Any]:
    """Get a specific log by ID."""
    try:
        log = await get_log_by_id(session=session, log_id=log_id)

        return {
            "id": log.id,
            "transaction_id": log.transaction_id,
            "datetime": log.datetime.isoformat() if log.datetime else None,
            "datatype": log.datatype,
            "data": log.data,
            "notes": log.notes,
        }

    except LuthienDBQueryError:
        raise HTTPException(status_code=404, detail=f"Log with ID {log_id} not found")
    except LuthienDBOperationError as db_err:
        logger.error(f"Database error getting log {log_id}: {db_err}")
        raise HTTPException(status_code=500, detail="Failed to retrieve log from database")
    except Exception as e:
        logger.error(f"Unexpected error getting log {log_id}: {e}")
        raise HTTPException(status_code=500, detail="An unexpected error occurred")


@router.get("/admin/logs-api/metadata/datatypes")
async def get_datatypes(
    session: AsyncSession = Depends(get_db_session),
) -> List[str]:
    """Get list of unique datatypes from logs."""
    try:
        return await get_unique_datatypes(session=session)
    except (LuthienDBQueryError, LuthienDBOperationError) as db_err:
        logger.error(f"Database error getting datatypes: {db_err}")
        raise HTTPException(status_code=500, detail="Failed to retrieve datatypes from database")
    except Exception as e:
        logger.error(f"Unexpected error getting datatypes: {e}")
        raise HTTPException(status_code=500, detail="An unexpected error occurred")


@router.get("/admin/logs-api/metadata/transaction-ids")
async def get_transaction_ids(
    limit: int = Query(100, ge=1, le=500, description="Maximum number of transaction IDs to return"),
    session: AsyncSession = Depends(get_db_session),
) -> List[str]:
    """Get list of unique transaction IDs from recent logs."""
    try:
        return await get_unique_transaction_ids(session=session, limit=limit)
    except (LuthienDBQueryError, LuthienDBOperationError) as db_err:
        logger.error(f"Database error getting transaction IDs: {db_err}")
        raise HTTPException(status_code=500, detail="Failed to retrieve transaction IDs from database")
    except Exception as e:
        logger.error(f"Unexpected error getting transaction IDs: {e}")
        raise HTTPException(status_code=500, detail="An unexpected error occurred")
