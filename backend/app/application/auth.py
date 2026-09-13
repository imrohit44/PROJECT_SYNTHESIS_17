from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from backend.app.domain.entities.customer import Customer
from backend.app.infrastructure.persistence.models import CustomerModel, UserModel
from backend.app.security.passwords import PasswordService
from backend.app.security.principal import CurrentUser
from backend.app.security.roles import UserRole
from backend.app.security.tokens import TokenError, TokenService


class AuthenticationError(Exception):
    """Raised for any invalid authentication attempt."""


@dataclass(frozen=True, slots=True)
class IssuedTokens:
    access_token: str
    refresh_token: str


class AuthApplicationService:
    def __init__(
        self,
        session_factory: sessionmaker[Session],
        password_service: PasswordService,
        token_service: TokenService,
    ) -> None:
        self._session_factory = session_factory
        self._passwords = password_service
        self._tokens = token_service

    def register(
        self, name: str, email: str, password: str, phone: str | None
    ) -> CurrentUser:
        normalized_email = email.lower()
        customer = Customer(name=name, email=normalized_email, phone=phone)
        user_id = str(uuid4())
        password_hash = self._passwords.hash(password)
        with self._session_factory.begin() as session:
            customer_model = CustomerModel(
                id=customer.customer_id,
                name=customer.name,
                email=normalized_email,
                phone=customer.phone,
            )
            session.add(customer_model)
            session.add(
                UserModel(
                    id=user_id,
                    customer_id=customer.customer_id,
                    email=normalized_email,
                    password_hash=password_hash,
                    role=UserRole.CUSTOMER.value,
                    is_active=True,
                )
            )
        return CurrentUser(
            user_id=user_id,
            customer_id=customer.customer_id,
            email=normalized_email,
            role=UserRole.CUSTOMER,
        )

    def authenticate(self, email: str, password: str) -> CurrentUser:
        with self._session_factory() as session:
            user = self._find_user(session, email)
            if user is None or not self._passwords.verify(password, user.password_hash):
                raise AuthenticationError("Invalid email or password")
            if not user.is_active:
                raise AuthenticationError("Invalid email or password")
            return self._principal(user)

    def issue_tokens(self, user: CurrentUser) -> IssuedTokens:
        return IssuedTokens(
            access_token=self._tokens.create_access_token(user.user_id, user.role),
            refresh_token=self._tokens.create_refresh_token(user.user_id, user.role),
        )

    def refresh(self, refresh_token: str) -> IssuedTokens:
        try:
            payload = self._tokens.decode(refresh_token, "refresh")
            user_id = str(payload["sub"])
        except (TokenError, KeyError, TypeError) as error:
            raise AuthenticationError("Invalid refresh token") from error
        user = self.get_current_user(user_id)
        return self.issue_tokens(user)

    def decode_access_token(self, token: str) -> str:
        try:
            return str(self._tokens.decode(token, "access")["sub"])
        except (TokenError, KeyError, TypeError) as error:
            raise AuthenticationError("Invalid authentication credentials") from error

    def get_current_user(self, user_id: str) -> CurrentUser:
        with self._session_factory() as session:
            user = session.get(UserModel, user_id)
            if user is None or not user.is_active:
                raise AuthenticationError("Invalid authentication credentials")
            return self._principal(user)

    def list_users(self) -> list[CurrentUser]:
        with self._session_factory() as session:
            users = session.scalars(select(UserModel).order_by(UserModel.email)).all()
            return [self._principal(user) for user in users]

    @staticmethod
    def _find_user(session: Session, email: str) -> UserModel | None:
        return session.execute(
            select(UserModel).where(UserModel.email == email.lower())
        ).scalar_one_or_none()

    @staticmethod
    def _principal(user: UserModel) -> CurrentUser:
        return CurrentUser(
            user_id=user.id,
            customer_id=user.customer_id,
            email=user.email,
            role=UserRole(user.role),
            is_active=user.is_active,
        )
