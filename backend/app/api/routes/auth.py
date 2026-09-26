"""Authentication, self-service sign-up and the caller's own profile."""
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_admin
from app.core.config import settings
from app.core.security import create_access_token, hash_password, verify_password
from app.db.session import get_db
from app.models import AuditLog, Role, User
from app.schemas import (LoginRequest, SignupRequest, TokenResponse,
                         UserCreate, UserOut)
from app.services.identity import next_auth_subject
from app.services.notifications import admin_ids, notify

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
    Admin-only: create an account with any role (student, lab staff, admin)
    and, optionally, its fingerprint/RFID subject. Public sign-up (below)
    can only ever create an un-enrolled student.
    """
    if db.scalar(select(User).where(User.email == req.email.lower())):
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered")
    if req.auth_subject and db.scalar(
            select(User).where(User.auth_subject == req.auth_subject)):
        raise HTTPException(status.HTTP_409_CONFLICT,
                            "auth_subject already assigned")

    subject = req.auth_subject or (
        next_auth_subject(db) if settings.AUTO_ASSIGN_AUTH_SUBJECT else None)
    user = User(email=req.email.lower(), full_name=req.full_name,
                hashed_password=hash_password(req.password), role=req.role,
                auth_subject=subject, student_id=req.student_id,
                department=req.department)
    db.add(user)
    db.flush()
    db.add(AuditLog(actor_user_id=admin.id, action="USER_CREATED",
                    entity_type="user", entity_id=str(user.id),
                    detail={"email": user.email, "role": user.role.value,
                            "auth_subject": user.auth_subject}))
    db.commit()
    db.refresh(user)
    return user


@router.get("/signup-config")
def signup_config():
    """What the login page needs to show (or hide) the sign-up form."""
    return {"enabled": settings.SIGNUP_ENABLED,
            "email_domains": settings.signup_domains,
            "requires_approval": settings.SIGNUP_REQUIRES_APPROVAL}


@router.post("/signup", status_code=status.HTTP_201_CREATED)
def signup(req: SignupRequest, request: Request, db: Session = Depends(get_db)):
    """
    Self-service sign-up. Always creates a STUDENT. With
    AUTO_ASSIGN_AUTH_SUBJECT it gets the next door identity (USERn), which
    opens nothing until staff enrol that person's fingerprint/face under the
    same number. Admins are notified of every new account.
    """
    if not settings.SIGNUP_ENABLED:
        raise HTTPException(status.HTTP_403_FORBIDDEN,
                            "Sign-up is disabled. Ask an administrator.")
    email = req.email.lower()
    domains = settings.signup_domains
    if domains and email.rsplit("@", 1)[-1] not in domains:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                            "Use your university email ("
                            + ", ".join("@" + d for d in domains) + ")")

    ip = request.client.host if request.client else None
    since = datetime.now(timezone.utc) - timedelta(hours=1)
    recent = db.scalar(select(func.count(AuditLog.id)).where(
        AuditLog.action == "USER_SIGNUP", AuditLog.ip_address == ip,
        AuditLog.created_at >= since)) or 0
    if recent >= settings.SIGNUPS_PER_IP_PER_HOUR:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS,
                            "Too many sign-ups from this network. Try later.")

    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(status.HTTP_409_CONFLICT,
                            "An account with this email already exists")

    pending = settings.SIGNUP_REQUIRES_APPROVAL
    user = User(email=email, full_name=req.full_name.strip(),
                hashed_password=hash_password(req.password),
                role=Role.STUDENT, student_id=req.student_id or None,
                auth_subject=(next_auth_subject(db)
                              if settings.AUTO_ASSIGN_AUTH_SUBJECT else None),
                department=req.department or None, is_active=not pending)
    db.add(user)
    db.flush()
    db.add(AuditLog(actor_user_id=user.id, action="USER_SIGNUP",
                    entity_type="user", entity_id=str(user.id), ip_address=ip,
                    detail={"email": email, "pending": pending,
                            "auth_subject": user.auth_subject}))
    notify(db, admin_ids(db), "USER_SIGNUP",
           f"New sign-up: {user.full_name}",
           body=(f"{email} created a student account."
                 + (" It is waiting for your approval." if pending else "")
                 + (f" Door identity {user.auth_subject}: enrol fingerprint "
                    f"slot {user.auth_subject[4:]} and face label "
                    f"{user.auth_subject} to give door access."
                    if user.auth_subject else "")),
           link="/admin/users", severity="warning" if pending else "info")
    db.commit()

    if pending:
        return {"pending_approval": True,
                "message": "Account created. An administrator must approve "
                           "it before you can sign in."}
    return {"pending_approval": False, **TokenResponse(
        access_token=create_access_token(user.id, user.role.value),
        role=user.role, user_id=user.id, full_name=user.full_name,
    ).model_dump(mode="json")}


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user
