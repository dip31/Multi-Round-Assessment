from fastapi import APIRouter
from app.services.memory_diagnostics import log_memory

from app.modules.aptitude.routers.aptitude_router import router as aptitude_router
from app.modules.aptitude.routers.admin_question_router import router as admin_question_router
from app.modules.auth.routers.auth_router import router as auth_router
from app.modules.session.routers.session_router import router as session_router

log_memory("startup: after authentication/session modules")

from app.modules.coding.routers.coding_router import router as coding_router
from app.modules.proctoring.routers.proctoring_router import router as proctoring_router
from app.modules.advanced_proctoring.routers.advanced_proctoring_router import router as advanced_proctoring_router

log_memory("startup: after coding/proctoring modules")

from app.modules.interview.routers.interview_router import router as interview_router
from app.modules.interview.routers.async_resume_router import router as async_resume_router
from app.modules.report.routers.report_router import router as report_router
from app.modules.report.routers.candidate_report_router import router as candidate_report_router

log_memory("startup: after interview modules")

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(auth_router)
api_router.include_router(session_router)
api_router.include_router(aptitude_router)
api_router.include_router(admin_question_router)
api_router.include_router(coding_router)
api_router.include_router(proctoring_router)
api_router.include_router(advanced_proctoring_router)
api_router.include_router(interview_router)
api_router.include_router(async_resume_router)
api_router.include_router(report_router)
api_router.include_router(candidate_report_router)
