from collections.abc import Callable

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from backend.app.api.dependencies import get_auth
from backend.app.application.auth import AuthApplicationService, AuthenticationError
from backend.app.application.banking import BankApplicationService
from backend.app.security.audit import security_event
from backend.app.security.principal import CurrentUser
from backend.app.security.roles import UserRole
from backend.app.security.tokens import TokenError

bearer = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    auth: AuthApplicationService = Depends(get_auth),
) -> CurrentUser:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication credentials are required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        return auth.get_current_user(auth.decode_access_token(credentials.credentials))
    except (TokenError, AuthenticationError, KeyError, TypeError) as error:
        security_event("authentication_failure")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        ) from error


def require_role(role: UserRole) -> Callable:
    def dependency(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if user.role is not role:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )
        return user

    return dependency


def authorize_customer(user: CurrentUser, customer_id: str) -> None:
    if user.role is not UserRole.ADMIN and user.customer_id != customer_id:
        security_event("authorization_failure", user_id=user.user_id)
        raise HTTPException(status_code=403, detail="Resource access is forbidden")


def authorize_account(
    account_id: str, user: CurrentUser, bank: BankApplicationService
) -> None:
    if user.role is UserRole.ADMIN:
        return
    if bank.account_owner_id(account_id) != user.customer_id:
        security_event("ownership_denial", user_id=user.user_id, account_id=account_id)
        raise HTTPException(status_code=403, detail="Resource access is forbidden")
