from fastapi import APIRouter, Depends

from backend.app.api.auth_dependencies import require_role
from backend.app.api.dependencies import get_auth
from backend.app.api.v1.auth import user_response
from backend.app.application.auth import AuthApplicationService
from backend.app.security.principal import CurrentUser
from backend.app.security.roles import UserRole
from backend.app.security.schemas import CurrentUserResponse

router = APIRouter(prefix="/users", tags=["users"])


@router.get(
    "",
    response_model=list[CurrentUserResponse],
    summary="List users for administrators",
)
def list_users(
    _: CurrentUser = Depends(require_role(UserRole.ADMIN)),
    auth: AuthApplicationService = Depends(get_auth),
) -> list[CurrentUserResponse]:
    return [user_response(user) for user in auth.list_users()]
