from dataclasses import dataclass

from backend.app.security.roles import UserRole


@dataclass(frozen=True, slots=True)
class CurrentUser:
    user_id: str
    customer_id: str
    email: str
    role: UserRole
    is_active: bool = True
