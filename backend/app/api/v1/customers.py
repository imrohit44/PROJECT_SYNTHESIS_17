from fastapi import APIRouter, Depends, status

from backend.app.api.auth_dependencies import (
    authorize_customer,
    get_current_user,
    require_role,
)
from backend.app.api.dependencies import get_bank, get_cache
from backend.app.api.v1.schemas import CreateCustomerRequest, CustomerResponse
from backend.app.api.v1.serializers import customer_response
from backend.app.application.banking import BankApplicationService
from backend.app.core.config import get_settings
from backend.app.infrastructure.cache import Cache
from backend.app.security.principal import CurrentUser
from backend.app.security.roles import UserRole

router = APIRouter(prefix="/customers", tags=["customers"])


@router.post(
    "",
    response_model=CustomerResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a customer",
)
def create_customer(
    request: CreateCustomerRequest,
    bank: BankApplicationService = Depends(get_bank),
    cache: Cache = Depends(get_cache),
    _: CurrentUser = Depends(require_role(UserRole.ADMIN)),
) -> CustomerResponse:
    customer = bank.register_customer(request.name, request.email, request.phone)
    cache.delete(f"customer:{customer.customer_id}")
    return customer_response(customer)


@router.get(
    "/{customer_id}",
    response_model=CustomerResponse,
    summary="Retrieve a customer",
)
def get_customer(
    customer_id: str,
    bank: BankApplicationService = Depends(get_bank),
    cache: Cache = Depends(get_cache),
    user: CurrentUser = Depends(get_current_user),
) -> CustomerResponse:
    authorize_customer(user, customer_id)
    key = f"customer:{customer_id}"
    cached = cache.get_json(key)
    if cached is not None:
        return CustomerResponse.model_validate(cached)
    response = customer_response(bank.find_customer(customer_id))
    cache.set_json(
        key,
        response.model_dump(mode="json"),
        get_settings().customer_cache_ttl_seconds,
    )
    return response
