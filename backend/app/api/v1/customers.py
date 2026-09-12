from fastapi import APIRouter, Depends, status

from backend.app.api.dependencies import get_bank
from backend.app.api.v1.schemas import CreateCustomerRequest, CustomerResponse
from backend.app.api.v1.serializers import customer_response
from backend.app.domain.entities.bank import Bank

router = APIRouter(prefix="/customers", tags=["customers"])


@router.post(
    "",
    response_model=CustomerResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a customer",
)
def create_customer(
    request: CreateCustomerRequest, bank: Bank = Depends(get_bank)
) -> CustomerResponse:
    customer = bank.register_customer(request.name, request.email, request.phone)
    return customer_response(customer)


@router.get(
    "/{customer_id}",
    response_model=CustomerResponse,
    summary="Retrieve a customer",
)
def get_customer(customer_id: str, bank: Bank = Depends(get_bank)) -> CustomerResponse:
    return customer_response(bank.find_customer(customer_id))
