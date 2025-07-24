"""Admin router for authentication and policy management."""

import json
import os
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Form, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from luthien_control.admin.auth import admin_auth_service
from luthien_control.admin.dependencies import csrf_protection, get_current_admin
from luthien_control.core.dependencies import get_db_session
from luthien_control.db.control_policy_crud import (
    get_policy_by_name,
    list_policies,
    save_policy_to_db,
)
from luthien_control.db.sqlmodel_models import ControlPolicy
from luthien_control.models.admin_user import AdminUser

# Template directory setup
templates_dir = os.path.join(os.path.dirname(__file__), "templates")
templates = Jinja2Templates(directory=templates_dir)

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request) -> HTMLResponse:
    """Display login page."""
    csrf_token = await csrf_protection.generate_token()
    response = templates.TemplateResponse(
        request,
        "login.html",
        {
            "csrf_token": csrf_token,
            "error": None,
        },
    )
    response.set_cookie(
        key="csrf_token",
        value=csrf_token,
        httponly=True,
        secure=request.url.scheme == "https",
        samesite="strict",
    )
    return response


@router.post("/login", response_model=None)
async def login(
    request: Request,
    response: Response,
    username: Annotated[str, Form()],
    password: Annotated[str, Form()],
    csrf_token: Annotated[str, Form(alias="csrf_token")],
    db: AsyncSession = Depends(get_db_session),
):
    """Handle login form submission."""
    # Validate CSRF token
    cookie_csrf = request.cookies.get("csrf_token")
    if not cookie_csrf or cookie_csrf != csrf_token:
        return templates.TemplateResponse(
            request,
            "login.html",
            {
                "csrf_token": await csrf_protection.generate_token(),
                "error": "Invalid request. Please try again.",
            },
            status_code=400,
        )

    # Authenticate user
    user = await admin_auth_service.authenticate(db, username, password)
    if not user:
        new_csrf = await csrf_protection.generate_token()
        response = templates.TemplateResponse(
            request,
            "login.html",
            {
                "csrf_token": new_csrf,
                "error": "Invalid username or password",
            },
            status_code=401,
        )
        response.set_cookie(
            key="csrf_token",
            value=new_csrf,
            httponly=True,
            secure=request.url.scheme == "https",
            samesite="strict",
        )
        return response  # type: ignore

    # Create session
    session = await admin_auth_service.create_session(db, user)

    redirect = RedirectResponse(url="/admin/policies", status_code=303)
    redirect.set_cookie(
        key="session_token",
        value=session.session_token,
        httponly=True,
        secure=request.url.scheme == "https",
        samesite="strict",
        max_age=86400,  # 24 hours
    )
    redirect.delete_cookie(key="csrf_token")

    return redirect


@router.get("/logout")
async def logout(
    request: Request,
    db: AsyncSession = Depends(get_db_session),
):
    """Logout and redirect to login page."""
    session_token = request.cookies.get("session_token")
    if session_token:
        await admin_auth_service.logout(db, session_token)

    redirect = RedirectResponse(url="/admin/login", status_code=303)
    redirect.delete_cookie(key="session_token")
    return redirect


@router.get("/", response_class=HTMLResponse)
async def admin_home(
    request: Request,
    current_admin: Annotated[AdminUser, Depends(get_current_admin)],
    db: AsyncSession = Depends(get_db_session),
) -> HTMLResponse:
    """Admin dashboard hub."""
    # Get some basic stats for the dashboard
    policies = await list_policies(db, active_only=False)
    active_policies = [p for p in policies if p.is_active]

    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "current_admin": current_admin,
            "total_policies": len(policies),
            "active_policies": len(active_policies),
        },
    )


@router.get("/policies", response_class=HTMLResponse)
async def policies_list(
    request: Request,
    current_admin: Annotated[AdminUser, Depends(get_current_admin)],
    db: AsyncSession = Depends(get_db_session),
) -> HTMLResponse:
    """List all control policies."""
    policies = await list_policies(db, active_only=False)

    return templates.TemplateResponse(
        request,
        "policies.html",
        {
            "current_admin": current_admin,
            "policies": policies,
        },
    )


@router.get("/policies/{policy_name}/edit", response_class=HTMLResponse)
async def edit_policy_page(
    request: Request,
    policy_name: str,
    current_admin: Annotated[AdminUser, Depends(get_current_admin)],
    db: AsyncSession = Depends(get_db_session),
) -> HTMLResponse:
    """Display policy edit page."""
    policy = await get_policy_by_name(db, policy_name)
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")

    csrf_token = await csrf_protection.generate_token()
    response = templates.TemplateResponse(
        request,
        "policy_edit.html",
        {
            "current_admin": current_admin,
            "policy": policy,
            "csrf_token": csrf_token,
            "config_json": json.dumps(policy.config, indent=2),
            "error": None,
        },
    )
    response.set_cookie(
        key="csrf_token",
        value=csrf_token,
        httponly=True,
        secure=request.url.scheme == "https",
        samesite="strict",
    )
    return response


@router.post("/policies/{policy_name}/edit", response_model=None)
async def update_policy_handler(
    request: Request,
    policy_name: str,
    config: Annotated[str, Form()],
    current_admin: Annotated[AdminUser, Depends(get_current_admin)],
    db: AsyncSession = Depends(get_db_session),
    description: Annotated[Optional[str], Form()] = None,
    is_active: Annotated[bool, Form()] = False,
    csrf_token: Annotated[str, Form(alias="csrf_token")] = "",
):
    """Handle policy update form submission."""
    # Validate CSRF token
    cookie_csrf = request.cookies.get("csrf_token")
    if not cookie_csrf or cookie_csrf != csrf_token:
        raise HTTPException(status_code=400, detail="Invalid request")

    # Get the policy first
    policy = await get_policy_by_name(db, policy_name)
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")

    # Parse and validate JSON config
    try:
        config_dict = json.loads(config)
    except json.JSONDecodeError as e:
        new_csrf = await csrf_protection.generate_token()
        response = templates.TemplateResponse(
            request,
            "policy_edit.html",
            {
                "current_admin": current_admin,
                "policy": policy,
                "csrf_token": new_csrf,
                "config_json": config,
                "error": f"Invalid JSON: {str(e)}",
            },
            status_code=400,
        )
        response.set_cookie(
            key="csrf_token",
            value=new_csrf,
            httponly=True,
            secure=request.url.scheme == "https",
            samesite="strict",
        )
        return response  # type: ignore

    # Update policy
    try:
        policy.config = config_dict
        if description is not None:
            policy.description = description
        policy.is_active = is_active

        db.add(policy)
        await db.commit()
        await db.refresh(policy)
    except Exception as e:
        new_csrf = await csrf_protection.generate_token()
        response = templates.TemplateResponse(
            request,
            "policy_edit.html",
            {
                "current_admin": current_admin,
                "policy": policy,
                "csrf_token": new_csrf,
                "config_json": config,
                "error": f"Update failed: {str(e)}",
            },
            status_code=400,
        )
        response.set_cookie(
            key="csrf_token",
            value=new_csrf,
            httponly=True,
            secure=request.url.scheme == "https",
            samesite="strict",
        )
        return response  # type: ignore

    redirect = RedirectResponse(url="/admin/policies", status_code=303)
    redirect.delete_cookie(key="csrf_token")
    return redirect


@router.get("/policies/new", response_class=HTMLResponse)
async def new_policy_page(
    request: Request,
    current_admin: Annotated[AdminUser, Depends(get_current_admin)],
) -> HTMLResponse:
    """Display new policy creation page."""
    csrf_token = await csrf_protection.generate_token()
    response = templates.TemplateResponse(
        request,
        "policy_new.html",
        {
            "current_admin": current_admin,
            "csrf_token": csrf_token,
            "error": None,
        },
    )
    response.set_cookie(
        key="csrf_token",
        value=csrf_token,
        httponly=True,
        secure=request.url.scheme == "https",
        samesite="strict",
    )
    return response


@router.post("/policies/new", response_model=None)
async def create_policy_handler(
    request: Request,
    name: Annotated[str, Form()],
    type: Annotated[str, Form()],
    config: Annotated[str, Form()],
    current_admin: Annotated[AdminUser, Depends(get_current_admin)],
    db: AsyncSession = Depends(get_db_session),
    description: Annotated[Optional[str], Form()] = None,
    is_active: Annotated[bool, Form()] = False,
    csrf_token: Annotated[str, Form(alias="csrf_token")] = "",
):
    """Handle new policy creation."""
    # Validate CSRF token
    cookie_csrf = request.cookies.get("csrf_token")
    if not cookie_csrf or cookie_csrf != csrf_token:
        raise HTTPException(status_code=400, detail="Invalid request")

    # Parse and validate JSON config
    try:
        config_dict = json.loads(config)
    except json.JSONDecodeError as e:
        new_csrf = await csrf_protection.generate_token()
        response = templates.TemplateResponse(
            request,
            "policy_new.html",
            {
                "current_admin": current_admin,
                "csrf_token": new_csrf,
                "error": f"Invalid JSON: {str(e)}",
                "form_data": {
                    "name": name,
                    "type": type,
                    "config": config,
                    "description": description,
                    "is_active": is_active,
                },
            },
            status_code=400,
        )
        response.set_cookie(
            key="csrf_token",
            value=new_csrf,
            httponly=True,
            secure=request.url.scheme == "https",
            samesite="strict",
        )
        return response  # type: ignore

    # Create new policy
    try:
        policy = ControlPolicy(
            name=name,
            type=type,
            config=config_dict,
            description=description,
            is_active=is_active,
        )
        await save_policy_to_db(db, policy)
    except Exception as e:
        new_csrf = await csrf_protection.generate_token()
        response = templates.TemplateResponse(
            request,
            "policy_new.html",
            {
                "current_admin": current_admin,
                "csrf_token": new_csrf,
                "error": f"Creation failed: {str(e)}",
                "form_data": {
                    "name": name,
                    "type": type,
                    "config": config,
                    "description": description,
                    "is_active": is_active,
                },
            },
            status_code=400,
        )
        response.set_cookie(
            key="csrf_token",
            value=new_csrf,
            httponly=True,
            secure=request.url.scheme == "https",
            samesite="strict",
        )
        return response  # type: ignore

    redirect = RedirectResponse(url="/admin/policies", status_code=303)
    redirect.delete_cookie(key="csrf_token")
    return redirect
