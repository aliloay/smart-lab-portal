"""Authentication and the caller's own profile."""
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_admin
from app.core.security import create_access_token, hash_password, verify_password
from app.db.session import get_db
from app.models import AuditLog, Role, User
from app.schemas import LoginRequest, TokenResponse, UserCreate, UserOut

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(req: LoginRequest, request: Request, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == req.email.lower()))

    # Same message and same work either way: a different response for "no such
    # user" would let anyone enumerate valid accounts.
    if user is None or not verify_password(req.password, user.hashed_password):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED,
                            "Incorrect email or password")
    if not user.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Account is disabled")

    db.add(AuditLog(actor_user_id=user.id, action="LOGIN", entity_type="user",
                    entity_id=str(user.id),
                    ip_address=request.client.host if request.client else None))
    db.commit()

    return TokenResponse(
        access_token=create_access_token(user.id, user.role.value),
        role=user.role, user_id=user.id, full_name=user.full_name,
    )


@router.post("/register", response_model=UserOut,
             status_code=status.HTTP_201_CREATED)
def register(req: UserCreate, db: Session = Depends(get_db),
             admin: User = Depends(require_admin)):
    """
    Admin-only. Self-service registration is deliberately not exposed: this
    system controls physical access to a laboratory, so account creation is an
    administrative act.
    """
    if db.scalar(select(User).where(User.email == req.email.lower())):
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered")
    if req.auth_subject and db.scalar(
            select(User).where(User.auth_subject == req.auth_subject)):
        raise HTTPException(status.HTTP_409_CONFLICT,
                            "auth_subject already assigned")

    user = User(email=req.email.lower(), full_name=req.full_name,
                hashed_password=hash_password(req.password), role=req.role,
                auth_subject=req.auth_subject, student_id=req.student_id,
                department=req.department)
    db.add(user)
    db.flush()
    db.add(AuditLog(actor_user_id=admin.id, action="USER_CREATED",
                    entity_type="user", entity_id=str(user.id),
                    detail={"email": user.email, "role": user.role.value}))
    db.commit()
    db.refresh(user)
    return user


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user
