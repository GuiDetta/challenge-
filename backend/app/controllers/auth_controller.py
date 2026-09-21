from fastapi import APIRouter, Depends

from app.schemas import UserCreate, UserLogin
from app.services.auth_service import AuthService
from app.services.container import get_auth_service

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", status_code=201)
def register(user_input: UserCreate, service: AuthService = Depends(get_auth_service)) -> dict:
    return service.register(user_input)


@router.post("/login")
def login(user_input: UserLogin, service: AuthService = Depends(get_auth_service)) -> dict:
    return service.login(user_input)
