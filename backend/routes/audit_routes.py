from fastapi import APIRouter

from backend.audit import get_logs, verify_audit_chain


router = APIRouter()


@router.get("/audit/logs")
def audit_logs(limit: int = 50):
    return {
        "logs": get_logs(limit),
    }


@router.get("/audit/verify")
def audit_verify():
    """
    校验审计日志哈希链是否完整。
    """
    return verify_audit_chain()
