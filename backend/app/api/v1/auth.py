from fastapi import APIRouter, Depends, status

from backend.app.api.auth_dependencies import get_current_user
from backend.app.api.dependencies import get_auth, get_login_limiter
from backend.app.application.auth import AuthApplicationService, AuthenticationError
from backend.app.security.audit import security_event
from backend.app.security.principal import CurrentUser
from backend.app.security.rate_limit import LoginRateLimiter
from backend.app.security.schemas import (
    CurrentUserResponse,
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
)

router = APIRouter(prefix="/auth", tags=["authentication"])


def user_response(user: CurrentUser) -> CurrentUserResponse:
    return CurrentUserResponse(
        user_id=user.user_id,
        customer_id=user.customer_id,
        email=user.email,
        role=user.role.value,
        is_active=user.is_active,
    )


@router.post(
    "/register",
    response_model=CurrentUserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a customer user",
)
def register(
    request: RegisterRequest, auth: AuthApplicationService = Depends(get_auth)
) -> CurrentUserResponse:
    user = auth.register(
        request.name, str(request.email), request.password, request.phone
    )
    security_event("registration_success", user_id=user.user_id)
    return user_response(user)


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Authenticate a user",
)
def login(
    request: LoginRequest,
    auth: AuthApplicationService = Depends(get_auth),
    limiter: LoginRateLimiter = Depends(get_login_limiter),
) -> TokenResponse:
    key = str(request.email).lower()
    if not limiter.allow(key):
        security_event("login_rate_limited", email=key)
        from fastapi import HTTPException

        raise HTTPException(status_code=429, detail="Too many authentication attempts")
    try:
        user = auth.authenticate(key, request.password)
    except AuthenticationError as error:
        security_event("login_failure", email=key)
        raise error
    security_event("login_success", user_id=user.user_id)
    tokens = auth.issue_tokens(user)
    return TokenResponse(
        access_token=tokens.access_token, refresh_token=tokens.refresh_token
    )


@router.post("/refresh", response_model=TokenResponse, summary="Refresh access tokens")
def refresh(
    request: RefreshRequest, auth: AuthApplicationService = Depends(get_auth)
) -> TokenResponse:
    tokens = auth.refresh(request.refresh_token)
    security_event("token_refresh")
    return TokenResponse(
        access_token=tokens.access_token, refresh_token=tokens.refresh_token
    )


@router.get("/me", response_model=CurrentUserResponse, summary="Get current user")
def me(user: CurrentUser = Depends(get_current_user)) -> CurrentUserResponse:
    return user_response(user)
