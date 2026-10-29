import pytest
from fastapi import FastAPI, APIRouter
from app.config import settings
from app.main import lifespan

@pytest.mark.asyncio
async def test_invariant_12_production_refuses_test_only_routes():
    """
    Invariant 12: Test-only code cannot reach production.
    The server refuses to start if ENV=production and any route tagged test_only is registered.
    """
    test_app = FastAPI(lifespan=lifespan)
    r = APIRouter(tags=["test_only"])
    @r.post("/test/endpoint")
    def dummy():
        return {"test": True}
    test_app.include_router(r)

    orig_env = settings.ENV
    try:
        settings.ENV = "production"
        with pytest.raises(RuntimeError, match="CRITICAL SECURITY VIOLATION: Route tagged 'test_only' is registered in production!"):
            async with test_app.router.lifespan_context(test_app):
                pass
    finally:
        settings.ENV = orig_env
