from fastapi import APIRouter

from backend.audit import get_logs


router = APIRouter()


@router.get("/audit/logs")
def audit_logs(limit: int = 50):
    return {
        "logs": get_logs(limit),
    }
