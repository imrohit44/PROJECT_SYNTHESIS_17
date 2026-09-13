from fastapi import APIRouter

from backend.app.api.v1 import accounts, auth, customers, health, transfers, users

router = APIRouter(prefix="/api/v1")
router.include_router(health.router)
router.include_router(auth.router)
router.include_router(customers.router)
router.include_router(accounts.router)
router.include_router(transfers.router)
router.include_router(users.router)
