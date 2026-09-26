"""Admin surface: events, sessions, users, devices, assets, alerts, summary, reports."""
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, desc, func, or_, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_admin, require_staff
from app.db.session import get_db
from app.models import (AccessEvent, AccessResult, AccessSession, Alert, Asset,
                        AssetStatus, AssetTransaction, AuditLog, AuthMethod,
                        Booking,
                        BookingStatus, Device, EventType, Issue, IssueSeverity,
                        Lab, RfidCredential, Role, User)
from app.schemas import (AdminSummary, AlertOut, AssetCreate, AssetDetail,
                         AssetInspect, AssetMaintenanceRow, AssetOut,
                         AssetTransactionOut, AssetUpdate, DeviceCreate,
                         DeviceOut, EventOut, LabOut, LifecycleEntry,
                         SessionOut, SessionTrace, UserBrief, UserOut,
                         UserUpdate)
from app.services.devices import device_out, is_fresh, refresh_liveness
from app.services.events import log_event
from app.services.issues import ACTIVE as ISSUE_ACTIVE, is_overdue
from app.services.sessions import close_expired, duration_minutes
from app.services.trace import DOOR_EVENTS, event_out, summarise

router = APIRouter(tags=["admin"])

# Event types that represent a security-relevant refusal or anomaly.
SECURITY_EVENTS = (EventType.ACCESS_DENIED, EventType.QR_REJECTED,
                   EventType.RFID_REJECTED, EventType.IDENTITY_MISMATCH,
                   EventType.FACE_REJECTED, EventType.FINGERPRINT_REJECTED,
                   EventType.ALARM)


def _utc(dt: datetime) -> datetime:
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None \
        else dt.astimezone(timezone.utc)


def _staff(u: User) -> bool:
    return u.role in (Role.ADMIN, Role.LAB_STAFF)


# ---------------------------------------------------------------- events ---
@router.get("/access-events", response_model=list[EventOut])
def access_events(
    lab_id: Optional[int] = None,
    user_id: Optional[int] = None,
    booking_id: Optional[int] = None,
    event_type: Optional[list[EventType]] = Query(None),
    method: Optional[AuthMethod] = None,
    result: Optional[AccessResult] = None,
    reason: Optional[str] = Query(None, max_length=48),
    security_only: bool = False,
    since: Optional[datetime] = None,
    until: Optional[datetime] = None,
    limit: int = Query(200, le=1000),
    db: Session = Depends(get_db),
    caller: User = Depends(get_current_user),
):
    """
    The access timeline.

    Staff and admins see everything. A STUDENT may read this too, but only
    their own events - which is what makes the "your recent access" panel on
    the student dashboard work at all.

    The scoping is forced server-side rather than trusted from the query
    string: a student who asks for somebody else's user_id is silently
    narrowed back to themselves instead of being refused, because refusing
    would leak whether that other user has any events.
    """
    if not _staff(caller):
        user_id = caller.id

    stmt = select(AccessEvent).order_by(desc(AccessEvent.created_at)).limit(limit)
    if lab_id is not None:
        stmt = stmt.where(AccessEvent.lab_id == lab_id)
    if user_id is not None:
        stmt = stmt.where(AccessEvent.user_id == user_id)
    if booking_id is not None:
        stmt = stmt.where(AccessEvent.booking_id == booking_id)
    if event_type:
        stmt = stmt.where(AccessEvent.event_type.in_(event_type))
    if security_only:
        stmt = stmt.where(AccessEvent.event_type.in_(SECURITY_EVENTS))
    if method is not None:
        stmt = stmt.where(AccessEvent.method == method)
    if result is not None:
        stmt = stmt.where(AccessEvent.result == result)
    if reason:
        stmt = stmt.where(AccessEvent.reason == reason)
    if since is not None:
        stmt = stmt.where(AccessEvent.created_at >= since)
    if until is not None:
        stmt = stmt.where(AccessEvent.created_at < until)

    labs = {l.id: l.code for l in db.scalars(select(Lab)).all()}
    users: dict[int, Optional[str]] = {}
    devices: dict[int, Optional[str]] = {}
    out = []
    for e in db.scalars(stmt).all():
        item = EventOut.model_validate(e)
        if e.user_id:
            if e.user_id not in users:
                u = db.get(User, e.user_id)
                users[e.user_id] = u.full_name if u else None
            item.user_name = users[e.user_id]
        if e.device_id:
            if e.device_id not in devices:
                d = db.get(Device, e.device_id)
                devices[e.device_id] = d.name if d else None
            item.device_name = devices[e.device_id]
        item.lab_code = labs.get(e.lab_id) if e.lab_id else None
        out.append(item)
    return out


# -------------------------------------------------------------- sessions ---
@router.get("/access-sessions", response_model=list[SessionOut])
def access_sessions(lab_id: Optional[int] = None,
                    open_only: bool = False,
                    limit: int = Query(200, le=1000),
                    db: Session = Depends(get_db),
                    _: User = Depends(require_staff)):
    """Every occupancy session - entry, door cycle, and how it ended."""
    close_expired(db)
    stmt = select(AccessSession).order_by(desc(AccessSession.started_at))
    if lab_id is not None:
        stmt = stmt.where(AccessSession.lab_id == lab_id)
    if open_only:
        stmt = stmt.where(AccessSession.ended_at.is_(None))
    labs = {l.id: l.code for l in db.scalars(select(Lab)).all()}
    out = []
    for s in db.scalars(stmt.limit(limit)).all():
        item = SessionOut.model_validate(s)
        u = db.get(User, s.user_id)
        item.user_name = u.full_name if u else None
        item.lab_code = labs.get(s.lab_id)
        item.duration_minutes = duration_minutes(s)
        out.append(item)
    return out


@router.get("/access-sessions/lookup")
def session_lookup(user_id: int, lab_id: int, at: datetime,
                   db: Session = Depends(get_db),
                   caller: User = Depends(get_current_user)):
    """
    The session a moment belongs to: the latest session of this person in
    this lab that had started by `at` (plus a short margin, because the grant
    is reported just after the biometric). Lets any access event link to its
    session. Students may only look themselves up.
    """
    if not _staff(caller) and user_id != caller.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Session not found")
    at = _utc(at)
    s = db.scalar(select(AccessSession).where(
        AccessSession.user_id == user_id, AccessSession.lab_id == lab_id,
        AccessSession.started_at <= at + timedelta(minutes=3))
        .order_by(desc(AccessSession.started_at)))
    # Too old to be the same visit when it ended well before `at`.
    if s is not None and s.ended_at is not None and             _utc(s.ended_at) < at - timedelta(minutes=3):
        s = None
    return {"session_id": s.id if s else None}


@router.get("/access-sessions/{session_id}", response_model=SessionTrace)
def session_detail(session_id: int, db: Session = Depends(get_db),
                   caller: User = Depends(get_current_user)):
    """
    One visit, end to end: the booking (if any), step 1 and its identity,
    step 2 and its identity, the grant, the door cycle, and an exit only if
    one was recorded. Works for RFID entries with no booking too.
    """
    close_expired(db)
    s = db.get(AccessSession, session_id)
    if s is None or (not _staff(caller) and s.user_id != caller.id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Session not found")
    user = db.get(User, s.user_id)
    lab = db.get(Lab, s.lab_id)

    start = _utc(s.started_at) - timedelta(minutes=3)
    end = (_utc(s.ended_at) if s.ended_at else datetime.now(timezone.utc))         + timedelta(minutes=1)
    conds = [and_(AccessEvent.user_id == s.user_id,
                  AccessEvent.lab_id == s.lab_id,
                  AccessEvent.event_type.in_(DOOR_EVENTS))]
    if s.booking_id:
        conds.append(and_(AccessEvent.booking_id == s.booking_id,
                          AccessEvent.event_type.in_(DOOR_EVENTS)))
    events = db.scalars(select(AccessEvent).where(
        or_(*conds), AccessEvent.created_at >= start,
        AccessEvent.created_at <= end).order_by(AccessEvent.created_at)).all()

    ses = SessionOut.model_validate(s)
    ses.user_name = user.full_name if user else None
    ses.lab_code = lab.code if lab else None
    ses.duration_minutes = duration_minutes(s)

    booking = None
    if s.booking_id:
        from app.api.routes.bookings import _decorate
        b = db.get(Booking, s.booking_id)
        booking = _decorate(db, b) if b else None

    return SessionTrace(
        session=ses,
        user=UserBrief(id=user.id, full_name=user.full_name, role=user.role,
                       auth_subject=user.auth_subject),
        lab=LabOut.model_validate(lab),
        booking=booking,
        summary=summarise(db, list(events), [s], user),
        events=[event_out(db, e, lab) for e in events])


# --------------------------------------------------------------- summary ---
@router.get("/summary", response_model=AdminSummary)
def summary(db: Session = Depends(get_db), _: User = Depends(require_staff)):
    close_expired(db)
    devices = refresh_liveness(db)
    now = datetime.now(timezone.utc)
    midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
    tomorrow = midnight + timedelta(days=1)

    labs = db.scalars(select(Lab)).all()
    confirmed = db.scalars(select(Booking).where(
        Booking.status == BookingStatus.CONFIRMED)).all()

    active = [b for b in confirmed
              if _utc(b.start_time) <= now <= _utc(b.end_time)]
    upcoming = [b for b in confirmed if _utc(b.start_time) > now]
    today = [b for b in confirmed
             if _utc(b.start_time) < tomorrow and _utc(b.end_time) > midnight]

    open_sessions = db.scalars(
        select(AccessSession).where(AccessSession.ended_at.is_(None))).all()
    occupied_lab_ids = {b.lab_id for b in active} | {s.lab_id for s in open_sessions}

    def count(*where) -> int:
        return db.scalar(select(func.count()).select_from(AccessEvent)
                         .where(*where)) or 0

    granted = count(AccessEvent.event_type == EventType.ACCESS_GRANTED,
                    AccessEvent.created_at >= midnight)
    denied = count(AccessEvent.event_type == EventType.ACCESS_DENIED,
                   AccessEvent.created_at >= midnight)
    security = count(AccessEvent.event_type.in_(SECURITY_EVENTS),
                     AccessEvent.created_at >= midnight)

    open_alerts = db.scalar(select(func.count()).select_from(Alert).where(
        Alert.is_resolved.is_(False))) or 0

    assets = db.scalars(select(Asset)).all()
    issues = db.scalars(select(Issue).where(Issue.status.in_(ISSUE_ACTIVE))).all()

    return AdminSummary(
        total_labs=len(labs), occupied_labs=len(occupied_lab_ids),
        active_bookings=len(active), upcoming_bookings=len(upcoming),
        granted_today=granted, denied_today=denied,
        devices_online=sum(1 for d in devices if is_fresh(d, now)),
        devices_total=len(devices),
        open_alerts=open_alerts,
        labs_with_hardware=sum(1 for l in labs if l.has_controller),
        active_users=db.scalar(select(func.count()).select_from(User).where(
            User.is_active.is_(True))) or 0,
        bookings_today=len(today),
        pending_bookings=db.scalar(select(func.count()).select_from(Booking).where(
            Booking.status == BookingStatus.PENDING,
            Booking.end_time > now)) or 0,
        people_inside=len(open_sessions),
        security_events_today=security,
        assets_total=len(assets),
        assets_in_maintenance=sum(1 for a in assets
                                  if a.status == AssetStatus.MAINTENANCE),
        assets_checked_out=sum(1 for a in assets
                               if a.status == AssetStatus.CHECKED_OUT),
        open_issues=len(issues),
        critical_issues=sum(1 for i in issues
                            if i.severity == IssueSeverity.CRITICAL),
        high_issues=sum(1 for i in issues if i.severity == IssueSeverity.HIGH),
        unassigned_issues=sum(1 for i in issues if i.assigned_to_id is None),
        overdue_issues=sum(1 for i in issues if is_overdue(i, now)),
    )


# ----------------------------------------------------------------- users ---
@router.get("/users", response_model=list[UserOut])
def list_users(db: Session = Depends(get_db), _: User = Depends(require_staff)):
    return db.scalars(select(User).order_by(User.full_name)).all()


@router.get("/users/next-auth-subject")
def next_subject(db: Session = Depends(get_db), _: User = Depends(require_admin)):
    """The door identity the next account would get (USERn = fingerprint slot n)."""
    from app.services.identity import next_auth_subject
    return {"auth_subject": next_auth_subject(db)}


@router.patch("/users/{user_id}", response_model=UserOut)
def update_user(user_id: int, req: UserUpdate, db: Session = Depends(get_db),
                admin: User = Depends(require_admin)):
    u = db.get(User, user_id)
    if u is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    changes = req.model_dump(exclude_unset=True)

    # An administrator cannot lock the system out of administration.
    if u.id == admin.id and (changes.get("is_active") is False or
                             changes.get("role") not in (None, Role.ADMIN)):
        raise HTTPException(status.HTTP_409_CONFLICT,
                            "You cannot demote or disable your own account")
    if "auth_subject" in changes:
        subj = (changes["auth_subject"] or "").strip() or None
        if subj and db.scalar(select(User).where(User.auth_subject == subj,
                                                 User.id != u.id)):
            raise HTTPException(status.HTTP_409_CONFLICT,
                                "auth_subject already assigned")
        changes["auth_subject"] = subj

    for k, v in changes.items():
        setattr(u, k, v)
    db.add(AuditLog(actor_user_id=admin.id, action="USER_UPDATED",
                    entity_type="user", entity_id=str(u.id),
                    detail={k: (v.value if hasattr(v, "value") else v)
                            for k, v in changes.items()}))
    db.commit()
    db.refresh(u)
    return u


@router.post("/users/{user_id}/rfid", status_code=status.HTTP_201_CREATED)
def add_rfid(user_id: int, uid_hex: str, label: str = "",
             db: Session = Depends(get_db), _: User = Depends(require_admin)):
    u = db.get(User, user_id)
    if u is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    uid = uid_hex.upper().replace(" ", "")
    if db.scalar(select(RfidCredential).where(RfidCredential.uid_hex == uid)):
        raise HTTPException(status.HTTP_409_CONFLICT, "UID already registered")
    cred = RfidCredential(uid_hex=uid, label=label, user_id=u.id)
    db.add(cred)
    db.commit()
    return {"id": cred.id, "uid_hex": cred.uid_hex, "user_id": u.id}


# --------------------------------------------------------------- devices ---
@router.get("/devices", response_model=list[DeviceOut])
def list_devices(lab_id: Optional[int] = None, db: Session = Depends(get_db),
                 _: User = Depends(require_staff)):
    """
    Liveness is recomputed on read: a device that stops sending heartbeats
    never gets a chance to mark itself offline. Staff only - the list
    includes network addresses.
    """
    now = datetime.now(timezone.utc)
    labs = {l.id: l.code for l in db.scalars(select(Lab)).all()}
    return [device_out(d, labs.get(d.lab_id), now)
            for d in refresh_liveness(db)
            if lab_id is None or d.lab_id == lab_id]


@router.post("/devices", response_model=DeviceOut,
             status_code=status.HTTP_201_CREATED)
def create_device(req: DeviceCreate, db: Session = Depends(get_db),
                  _: User = Depends(require_admin)):
    if db.scalar(select(Device).where(Device.device_uid == req.device_uid)):
        raise HTTPException(status.HTTP_409_CONFLICT, "device_uid exists")
    if db.get(Lab, req.lab_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Lab not found")
    d = Device(**req.model_dump())
    db.add(d)
    db.commit()
    db.refresh(d)
    return device_out(d)


# ---------------------------------------------------------------- assets ---
def _asset_out(db: Session, a: Asset, labs: dict[int, Lab],
               open_counts: Counter, viewer: Optional[User] = None,
               now: Optional[datetime] = None) -> AssetOut:
    now = now or datetime.now(timezone.utc)
    out = AssetOut.model_validate(a)
    lab = labs.get(a.lab_id)
    out.lab_code = lab.code if lab else None
    out.lab_name = lab.name if lab else None
    out.lab_location = lab.location if lab else None
    out.open_issues = open_counts.get(a.id, 0)
    out.maintenance_due = (a.next_maintenance_at is not None
                           and _utc(a.next_maintenance_at) <= now)
    # Who is holding an item is personal data: staff see the name.
    if a.holder_id and viewer is not None and _staff(viewer):
        h = db.get(User, a.holder_id)
        out.holder_name = h.full_name if h else None
    else:
        out.holder_id = None
    return out


def _open_counts(db: Session, asset_id: Optional[int] = None) -> Counter:
    stmt = select(Issue.asset_id).where(Issue.asset_id.is_not(None),
                                        Issue.status.in_(ISSUE_ACTIVE))
    if asset_id is not None:
        stmt = stmt.where(Issue.asset_id == asset_id)
    return Counter(db.scalars(stmt).all())


def _labs(db: Session) -> dict[int, Lab]:
    return {l.id: l for l in db.scalars(select(Lab)).all()}


@router.get("/assets", response_model=list[AssetOut])
def list_assets(lab_id: Optional[int] = None, due: bool = False,
                db: Session = Depends(get_db),
                user: User = Depends(get_current_user)):
    stmt = select(Asset).order_by(Asset.name)
    if lab_id is not None:
        stmt = stmt.where(Asset.lab_id == lab_id)
    labs, counts, now = _labs(db), _open_counts(db), datetime.now(timezone.utc)
    rows = [_asset_out(db, a, labs, counts, user, now)
            for a in db.scalars(stmt).all()]
    return [r for r in rows if r.maintenance_due] if due else rows


@router.get("/assets/{asset_id}", response_model=AssetDetail)
def asset_detail(asset_id: int, db: Session = Depends(get_db),
                 user: User = Depends(get_current_user)):
    """
    The equipment's record: where it is, who has it, when it was last
    inspected, when maintenance is due, and everything that went wrong.
    """
    a = db.get(Asset, asset_id)
    if a is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Asset not found")
    labs = _labs(db)
    staff = _staff(user)
    names: dict[int, Optional[str]] = {}

    def name(uid: Optional[int]) -> Optional[str]:
        if uid is None:
            return None
        if uid not in names:
            u = db.get(User, uid)
            names[uid] = u.full_name if u else None
        return names[uid]

    txs = db.scalars(select(AssetTransaction).where(
        AssetTransaction.asset_id == a.id)
        .order_by(desc(AssetTransaction.created_at)).limit(200)).all()
    tx_out = []
    if staff:
        for t in txs[:50]:
            item = AssetTransactionOut.model_validate(t)
            item.user_name = name(t.user_id)
            tx_out.append(item)

    issues = db.scalars(select(Issue).where(Issue.asset_id == a.id)
                        .order_by(desc(Issue.created_at))).all()
    history = []
    for i in issues:
        history.append(AssetMaintenanceRow(
            id=i.id, ticket_number=i.ticket_number, title=i.title,
            category=i.category, severity=i.severity, status=i.status,
            created_at=i.created_at, resolved_at=i.resolved_at,
            technician=name(i.assigned_to_id),
            resolution_notes=i.resolution_notes or "",
            is_mine=i.reporter_id == user.id))

    # One timeline of the item's life. Check-outs name the borrower, so
    # they are only part of it for staff.
    life: list[LifecycleEntry] = []
    for i in issues:
        life.append(LifecycleEntry(
            at=i.created_at, kind="ISSUE_REPORTED", issue_id=i.id,
            title=f"{i.ticket_number} reported - {i.title}",
            detail=f"{i.severity.value.title()} · {i.category.value.replace('_', ' ').title()}"))
        if i.resolved_at:
            life.append(LifecycleEntry(
                at=i.resolved_at, kind="ISSUE_RESOLVED", issue_id=i.id,
                title=f"{i.ticket_number} resolved",
                detail=i.resolution_notes or "",
                actor=name(i.assigned_to_id) if staff else None))
    for t in txs:
        if t.action == "INSPECTION":
            life.append(LifecycleEntry(at=t.created_at, kind="INSPECTION",
                                       title="Inspected", detail=t.note or "",
                                       actor=name(t.user_id) if staff else None))
        elif t.action.startswith("STATUS_"):
            life.append(LifecycleEntry(
                at=t.created_at, kind="STATUS",
                title=f"Status changed to {t.action[7:].replace('_', ' ').lower()}",
                detail=t.note or "", actor=name(t.user_id) if staff else None))
        elif staff and t.action in ("CHECKOUT", "RETURN"):
            life.append(LifecycleEntry(
                at=t.created_at, kind=t.action,
                title="Checked out" if t.action == "CHECKOUT" else "Returned",
                detail=t.note or "", actor=name(t.user_id)))
    life.sort(key=lambda e: _utc(e.at), reverse=True)

    return AssetDetail(
        asset=_asset_out(db, a, labs, _open_counts(db, a.id), user),
        lab=LabOut.model_validate(labs[a.lab_id]),
        transactions=tx_out, maintenance=history, lifecycle=life)


@router.post("/assets", response_model=AssetOut,
             status_code=status.HTTP_201_CREATED)
def create_asset(req: AssetCreate, db: Session = Depends(get_db),
                 user: User = Depends(require_staff)):
    if db.scalar(select(Asset).where(Asset.asset_tag == req.asset_tag)):
        raise HTTPException(status.HTTP_409_CONFLICT, "asset_tag exists")
    if db.get(Lab, req.lab_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Lab not found")
    a = Asset(**req.model_dump())
    db.add(a)
    db.commit()
    db.refresh(a)
    return _asset_out(db, a, _labs(db), Counter(), user)


@router.patch("/assets/{asset_id}", response_model=AssetOut)
def update_asset(asset_id: int, req: AssetUpdate, db: Session = Depends(get_db),
                 user: User = Depends(require_staff)):
    a = db.get(Asset, asset_id)
    if a is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Asset not found")
    changes = req.model_dump(exclude_unset=True)
    new_status = changes.get("status")
    if new_status is not None and new_status != a.status:
        db.add(AssetTransaction(asset_id=a.id, user_id=user.id, lab_id=a.lab_id,
                                action=f"STATUS_{new_status.value}",
                                note=f"{a.status.value} → {new_status.value}"))
        # Leaving CHECKED_OUT any other way than a return still ends the loan.
        if a.status == AssetStatus.CHECKED_OUT:
            a.holder_id = None
            a.checked_out_at = None
    for k, v in changes.items():
        setattr(a, k, v)
    db.commit()
    db.refresh(a)
    return _asset_out(db, a, _labs(db), _open_counts(db, a.id), user)


@router.post("/assets/{asset_id}/inspect", response_model=AssetOut)
def inspect_asset(asset_id: int, req: AssetInspect,
                  db: Session = Depends(get_db),
                  user: User = Depends(require_staff)):
    """Record an inspection now, and optionally when the next one is due."""
    a = db.get(Asset, asset_id)
    if a is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Asset not found")
    now = datetime.now(timezone.utc)
    if req.next_maintenance_at is not None and _utc(req.next_maintenance_at) <= now:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                            "The next maintenance date must be in the future")
    a.last_inspected_at = now
    if req.next_maintenance_at is not None:
        a.next_maintenance_at = req.next_maintenance_at
    db.add(AssetTransaction(asset_id=a.id, user_id=user.id, lab_id=a.lab_id,
                            action="INSPECTION", note=req.note.strip()))
    db.commit()
    db.refresh(a)
    return _asset_out(db, a, _labs(db), _open_counts(db, a.id), user)


@router.post("/assets/{asset_id}/checkout", response_model=AssetOut)
def checkout_asset(asset_id: int, db: Session = Depends(get_db),
                   user: User = Depends(get_current_user)):
    a = db.get(Asset, asset_id)
    if a is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Asset not found")
    if a.status != AssetStatus.AVAILABLE:
        raise HTTPException(status.HTTP_409_CONFLICT,
                            f"Asset is {a.status.value}")
    a.status = AssetStatus.CHECKED_OUT
    a.holder_id = user.id
    a.checked_out_at = datetime.now(timezone.utc)
    db.add(AssetTransaction(asset_id=a.id, user_id=user.id, lab_id=a.lab_id,
                            action="CHECKOUT"))
    log_event(db, EventType.ASSET_CHECKOUT, lab_id=a.lab_id, user_id=user.id,
              message=f"{user.full_name} checked out {a.name}")
    db.commit()
    db.refresh(a)
    return _asset_out(db, a, _labs(db), _open_counts(db, a.id), user)


@router.post("/assets/{asset_id}/return", response_model=AssetOut)
def return_asset(asset_id: int, db: Session = Depends(get_db),
                 user: User = Depends(get_current_user)):
    a = db.get(Asset, asset_id)
    if a is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Asset not found")
    if a.status != AssetStatus.CHECKED_OUT:
        raise HTTPException(status.HTTP_409_CONFLICT,
                            f"Asset is {a.status.value}, not checked out")
    # Only the borrower or staff can return an item.
    if not _staff(user) and a.holder_id not in (None, user.id):
        raise HTTPException(status.HTTP_403_FORBIDDEN,
                            "Only the person who checked it out, or staff, "
                            "can return this item")
    a.status = AssetStatus.AVAILABLE
    a.holder_id = None
    a.checked_out_at = None
    db.add(AssetTransaction(asset_id=a.id, user_id=user.id, lab_id=a.lab_id,
                            action="RETURN"))
    log_event(db, EventType.ASSET_RETURN, lab_id=a.lab_id, user_id=user.id,
              message=f"{user.full_name} returned {a.name}")
    db.commit()
    db.refresh(a)
    return _asset_out(db, a, _labs(db), _open_counts(db, a.id), user)


# ---------------------------------------------------------------- alerts ---
def _alert_out(a: Alert, labs: dict[int, str]) -> AlertOut:
    out = AlertOut.model_validate(a)
    out.lab_code = labs.get(a.lab_id) if a.lab_id else None
    return out


@router.get("/alerts", response_model=list[AlertOut])
def list_alerts(open_only: bool = False, db: Session = Depends(get_db),
                _: User = Depends(require_staff)):
    refresh_liveness(db)
    stmt = select(Alert).order_by(desc(Alert.created_at)).limit(200)
    if open_only:
        stmt = stmt.where(Alert.is_resolved.is_(False))
    labs = {l.id: l.code for l in db.scalars(select(Lab)).all()}
    return [_alert_out(a, labs) for a in db.scalars(stmt).all()]


@router.post("/alerts/{alert_id}/resolve", response_model=AlertOut)
def resolve_alert(alert_id: int, db: Session = Depends(get_db),
                  _: User = Depends(require_staff)):
    a = db.get(Alert, alert_id)
    if a is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Alert not found")
    a.is_resolved = True
    a.resolved_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(a)
    labs = {l.id: l.code for l in db.scalars(select(Lab)).all()}
    return _alert_out(a, labs)


@router.get("/access-events/export")
def export_events(lab_id: Optional[int] = None,
                  since: Optional[datetime] = None,
                  db: Session = Depends(get_db),
                  _: User = Depends(require_staff)):
    """
    CSV of the audit trail, resolved to names rather than foreign keys, so it
    can go straight into a thesis appendix or a spreadsheet.
    """
    import csv
    import io

    from fastapi.responses import StreamingResponse

    stmt = select(AccessEvent).order_by(desc(AccessEvent.created_at)).limit(5000)
    if lab_id is not None:
        stmt = stmt.where(AccessEvent.lab_id == lab_id)
    if since is not None:
        stmt = stmt.where(AccessEvent.created_at >= since)

    labs = {l.id: l.code for l in db.scalars(select(Lab)).all()}
    users = {u.id: u.full_name for u in db.scalars(select(User)).all()}

    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["timestamp", "lab", "event_type", "person", "method",
                "result", "reason", "booking_id", "message"])
    for e in db.scalars(stmt).all():
        w.writerow([
            e.created_at.isoformat() if e.created_at else "",
            labs.get(e.lab_id, ""),
            e.event_type.value if e.event_type else "",
            users.get(e.user_id, ""),
            e.method.value if e.method else "",
            e.result.value if e.result else "",
            e.reason or "",
            e.booking_id or "",
            e.message or "",
        ])
    buf.seek(0)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M")
    return StreamingResponse(
        iter([buf.getvalue()]), media_type="text/csv",
        headers={"Content-Disposition":
                 f'attachment; filename="access-events-{stamp}.csv"'})


# --------------------------------------------------------------- reports ---
@router.get("/reports/access")
def access_report(days: int = Query(7, le=90), db: Session = Depends(get_db),
                  _: User = Depends(require_staff)):
    """
    Daily grant/deny counts per lab. Real aggregates over real rows - if
    nothing has happened, the series is empty rather than padded.
    """
    since = datetime.now(timezone.utc) - timedelta(days=days)
    rows = db.execute(
        select(AccessEvent.lab_id,
               func.date(AccessEvent.created_at).label("day"),
               AccessEvent.event_type,
               func.count().label("n"))
        .where(AccessEvent.created_at >= since,
               AccessEvent.event_type.in_([EventType.ACCESS_GRANTED,
                                           EventType.ACCESS_DENIED]))
        .group_by(AccessEvent.lab_id, "day", AccessEvent.event_type)
        .order_by("day")).all()

    labs = {l.id: l.code for l in db.scalars(select(Lab)).all()}
    return [{"lab": labs.get(r.lab_id), "day": str(r.day),
             "event": r.event_type.value if hasattr(r.event_type, "value")
             else str(r.event_type),
             "count": r.n} for r in rows]


@router.get("/reports/overview")
def reports_overview(days: int = Query(30, ge=1, le=365),
                     db: Session = Depends(get_db),
                     _: User = Depends(require_staff)):
    """
    Every aggregate the reports page draws, from real rows only. A section
    with nothing behind it comes back empty and the page says "not enough
    data yet" - nothing is interpolated, smoothed or sampled.

    Hours are returned in UTC; the browser shifts them to local time.
    """
    now = datetime.now(timezone.utc)
    since = now - timedelta(days=days)
    labs = {l.id: l for l in db.scalars(select(Lab)).all()}

    bookings = db.scalars(select(Booking).where(
        Booking.start_time >= since, Booking.start_time <= now + timedelta(days=60))
    ).all()
    live = [b for b in bookings
            if b.status in (BookingStatus.CONFIRMED, BookingStatus.COMPLETED)]

    by_lab: dict[int, dict] = defaultdict(lambda: {"count": 0, "hours": 0.0,
                                                   "used": 0})
    for b in live:
        r = by_lab[b.lab_id]
        r["count"] += 1
        r["hours"] += (_utc(b.end_time) - _utc(b.start_time)).total_seconds() / 3600
        if b.first_entry_at is not None:
            r["used"] += 1

    volume = Counter(_utc(b.start_time).date().isoformat() for b in live
                     if _utc(b.start_time) <= now)
    hours = Counter(_utc(b.start_time).hour for b in live)

    past = [b for b in live if _utc(b.end_time) < now]
    used = [b for b in past if b.first_entry_at is not None]

    buckets = {"early": 0, "on_time": 0, "late_5_15": 0, "late_15_30": 0,
               "late_30_plus": 0}
    for b in live:
        if b.first_entry_at is None:
            continue
        d = (_utc(b.first_entry_at) - _utc(b.start_time)).total_seconds() / 60
        if d < -5:
            buckets["early"] += 1
        elif d <= 5:
            buckets["on_time"] += 1
        elif d <= 15:
            buckets["late_5_15"] += 1
        elif d <= 30:
            buckets["late_15_30"] += 1
        else:
            buckets["late_30_plus"] += 1

    events = db.execute(
        select(func.date(AccessEvent.created_at).label("day"),
               AccessEvent.event_type, func.count().label("n"))
        .where(AccessEvent.created_at >= since,
               AccessEvent.event_type.in_([EventType.ACCESS_GRANTED,
                                           EventType.ACCESS_DENIED]))
        .group_by("day", AccessEvent.event_type).order_by("day")).all()
    outcomes: dict[str, dict] = {}
    for r in events:
        row = outcomes.setdefault(str(r.day), {"day": str(r.day), "granted": 0,
                                               "denied": 0})
        key = "granted" if r.event_type == EventType.ACCESS_GRANTED else "denied"
        row[key] += r.n

    reasons = db.execute(
        select(AccessEvent.reason, func.count().label("n"))
        .where(AccessEvent.created_at >= since,
               AccessEvent.event_type.in_(SECURITY_EVENTS),
               AccessEvent.reason.is_not(None))
        .group_by(AccessEvent.reason).order_by(desc("n"))).all()

    checkouts = db.execute(
        select(AssetTransaction.asset_id, func.count().label("n"))
        .where(AssetTransaction.created_at >= since,
               AssetTransaction.action == "CHECKOUT")
        .group_by(AssetTransaction.asset_id).order_by(desc("n")).limit(10)).all()
    assets = {a.id: a for a in db.scalars(select(Asset)).all()}

    sessions = db.scalars(select(AccessSession).where(
        AccessSession.started_at >= since)).all()
    entries_by_hour = Counter(_utc(s.started_at).hour for s in sessions)

    return {
        "period_days": days,
        "generated_at": now.isoformat(),
        "bookings_by_lab": sorted(
            [{"label": labs[k].code if k in labs else str(k),
              "name": labs[k].name if k in labs else "",
              "count": v["count"], "hours": round(v["hours"], 1),
              "used": v["used"]} for k, v in by_lab.items()],
            key=lambda r: -r["count"]),
        "booking_volume": [{"day": d, "count": n}
                           for d, n in sorted(volume.items())],
        "booking_hours_utc": [{"hour": h, "count": n}
                              for h, n in sorted(hours.items())],
        "entry_hours_utc": [{"hour": h, "count": n}
                            for h, n in sorted(entries_by_hour.items())],
        "utilisation": {
            "bookings": len(live),
            "finished": len(past),
            "used": len(used),
            "no_show": len(past) - len(used),
            "used_rate": round(len(used) / len(past), 3) if past else None,
        },
        "entry_delays": buckets if any(buckets.values()) else {},
        "access_outcomes": list(outcomes.values()),
        "denial_reasons": [{"reason": r.reason, "count": r.n} for r in reasons],
        "asset_checkouts": [{"label": assets[r.asset_id].name
                             if r.asset_id in assets else str(r.asset_id),
                             "count": r.n} for r in checkouts],
    }
