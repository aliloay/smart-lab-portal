"""Authentication, self-service sign-up and the caller's own profile."""
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_admin
from app.core.config import settings
from app.core import throttle, usernames
from app.core.security import create_access_token, hash_password, verify_and_upgrade
from app.db.session import get_db
from app.models import AuditLog, Role, User
from app.schemas import (LoginRequest, SignupRequest, TokenResponse,
                         UserCreate, UserOut)
from app.services import enrolment
from app.services.identity import next_auth_subject
from app.services.notifications import admin_ids, notify

router = APIRouter(prefix="/auth", tags=["auth"])


def _username_or_422(db: Session, name: str | None, user_id: int | None = None) -> str | None:
    """Normalised username, or 422 (format) / 409 (taken). None stays None."""
    try:
        n = usernames.normalize(name)
    except ValueError as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(e))
    if n and db.scalar(select(User).where(User.username == n, User.id != (user_id or -1))):
        raise HTTPException(status.HTTP_409_CONFLICT, f"The username {n} is already taken")
    return n


@router.get("/username-suggestion")
def username_suggestion(full_name: str = Query(min_length=1, max_length=255)):
    """firstname.lastname from a name (the sign-up and Add user forms pre-fill it)."""
    return {"username": usernames.suggest(full_name)}


@router.post("/login", response_model=TokenResponse)
def login(req: LoginRequest, request: Request, db: Session = Depends(get_db)):
    ident = req.email.strip().lower()             # e-mail or username (2026-10-20)
    ip = request.client.host if request.client else None
    account_key, address_key = f"acct:{ident}", f"ip:{ip}"
    wait = max(throttle.login_by_account.blocked_for(account_key),
               throttle.login_by_address.blocked_for(address_key))
    if wait > 0:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS,
                            f"Too many failed sign-ins. Try again in {int(wait // 60) + 1} min.",
                            headers={"Retry-After": str(int(wait) + 1)})
    user = db.scalar(select(User).where(User.email == ident if "@" in ident else User.username == ident))

    # Same message and same work either way: a different response for "no such
    # user" would let anyone enumerate valid accounts.
    ok, new_hash = verify_and_upgrade(req.password, user.hashed_password if user else None)
    if not ok:
        throttle.login_by_account.fail(account_key)
        throttle.login_by_address.fail(address_key)
        # Logged without the password; the attempted email only when it is a real account.
        db.add(AuditLog(actor_user_id=user.id if user else None, action="LOGIN_FAILED",
                        entity_type="user", entity_id=str(user.id) if user else None,
                        detail={"known_account": user is not None}, ip_address=ip))
        db.commit()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED,
                            "Incorrect email / username or password")
    if not user.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Account is disabled")
    throttle.login_by_account.clear(account_key)
    if new_hash:                                     # bcrypt -> Argon2id on a successful sign-in
        user.hashed_password = new_hash

    db.add(AuditLog(actor_user_id=user.id, action="LOGIN", entity_type="user",
                    entity_id=str(user.id), ip_address=ip))
    # Accounts made before this reminder existed get it on their next sign-in
    # (once - the dedupe key stops repeats; the banner shows every time).
    enrolment.welcome(db, user)
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
    username = _username_or_422(db, req.username)
    if req.auth_subject and db.scalar(
            select(User).where(User.auth_subject == req.auth_subject)):
        raise HTTPException(status.HTTP_409_CONFLICT,
                            "auth_subject already assigned")

    subject = req.auth_subject or (
        next_auth_subject(db) if settings.AUTO_ASSIGN_AUTH_SUBJECT else None)
    user = User(email=req.email.lower(), username=username, full_name=req.full_name,
                hashed_password=hash_password(req.password), role=req.role,
                auth_subject=subject, student_id=req.student_id,
                department=req.department)
    db.add(user)
    db.flush()
    db.add(AuditLog(actor_user_id=admin.id, action="USER_CREATED",
                    entity_type="user", entity_id=str(user.id),
                    detail={"email": user.email, "role": user.role.value,
                            "auth_subject": user.auth_subject}))
    enrolment.welcome(db, user)
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
    username = _username_or_422(db, req.username)

    pending = settings.SIGNUP_REQUIRES_APPROVAL
    user = User(email=email, username=username, full_name=req.full_name.strip(),
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
    enrolment.welcome(db, user)
    db.commit()

    if pending:
        return {"pending_approval": True,
                "message": "Account created. An administrator must approve "
                           "it before you can sign in."}
    return {"pending_approval": False, **TokenResponse(
        access_token=create_access_token(user.id, user.role.value),
        role=user.role, user_id=user.id, full_name=user.full_name,
    ).model_dump(mode="json")}


@router.post("/ws-ticket")
def ws_ticket(user: User = Depends(get_current_user)):
    """A one-time, 30-second ticket for the live-updates WebSocket (core/ws_ticket.py): the sign-in token
    itself never goes into a URL."""
    from app.core import ws_ticket as tickets
    return {"ticket": tickets.issue(user.id), "expires_in": int(tickets.TICKET_S)}


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user


@router.get("/me/access-setup")
def my_access_setup(user: User = Depends(get_current_user)):
    """What this person still needs before a lab door will open for them."""
    return enrolment.status(user)


# ------------------------------------------------------- personal door QR ---
# A card that lives in a QR code (e.g. in the phone's Wallet). Shown once:
# only its hash is stored. Same rules as an RFID card at the door.
@router.post("/me/door-qr")
def create_my_door_qr(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    import base64
    from app.services.access import issue_personal_qr
    from app.services.qr import render_qr_png
    if not user.auth_subject:
        raise HTTPException(status.HTTP_409_CONFLICT,
                            "Your door identity is not set up yet - ask lab staff to enrol you first.")
    token = issue_personal_qr(db, user)
    db.add(AuditLog(actor_user_id=user.id, action="PERSONAL_QR_ISSUED",
                    entity_type="user", entity_id=str(user.id), detail={}))
    db.commit()
    png = render_qr_png(token)
    return {"payload": token,
            "png_base64": base64.b64encode(png).decode() if png else None,
            "message": "Any earlier door QR of yours no longer works."}


@router.get("/me/door-qr")
def my_door_qr_status(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    from app.models import PersonalQrCredential
    cred = db.scalar(select(PersonalQrCredential).where(
        PersonalQrCredential.user_id == user.id, PersonalQrCredential.revoked_at.is_(None)))
    return {"active": cred is not None, "issued_at": cred.issued_at if cred else None}


@router.delete("/me/door-qr")
def revoke_my_door_qr(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    from app.models import PersonalQrCredential
    now = datetime.now(timezone.utc)
    n = 0
    for c in db.scalars(select(PersonalQrCredential).where(
            PersonalQrCredential.user_id == user.id, PersonalQrCredential.revoked_at.is_(None))).all():
        c.revoked_at = now
        n += 1
    db.add(AuditLog(actor_user_id=user.id, action="PERSONAL_QR_REVOKED",
                    entity_type="user", entity_id=str(user.id), detail={"revoked": n}))
    db.commit()
    return {"revoked": n}
