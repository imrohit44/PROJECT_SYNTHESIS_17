from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health", summary="Check application liveness")
async def health_check() -> dict[str, str]:
    """Confirm that the application process is running."""

    return {"status": "ok"}
