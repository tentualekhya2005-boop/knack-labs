from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr

from app.core.rate_limit import rate_limit_login
from app.core.security import MOCK_USERS, create_access_token

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    email: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    principal_id: str


@router.post(
    "/login",
    response_model=LoginResponse,
    dependencies=[Depends(rate_limit_login)],
)
def login(credentials: LoginRequest):
    user = MOCK_USERS.get(credentials.email)
    if not user or user["password"] != credentials.password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    token = create_access_token(
        data={
            "sub": credentials.email,
            "principal_id": user["principal_id"],
        }
    )
    return LoginResponse(access_token=token, principal_id=user["principal_id"])

