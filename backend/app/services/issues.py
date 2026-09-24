"""
Laboratory issue reporting and the maintenance workflow.

Everything that decides who may do what lives here, in one place, and the
routes only translate its answers into HTTP. The frontend receives the same
answers as `can_*` flags, so it never offers an action this module would
refuse - but it is this module, not the UI, that enforces them.

Every change writes an IssueHistory row in the same transaction as the change
itself: the timeline a student sees and the audit trail an administrator
reads are the same rows.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import (AccessEvent, Asset, Device, Issue, IssueComment,
                        IssueEventType, IssueHistory, IssuePhoto,
                        IssuePhotoStage, IssueSeverity, IssueStatus, Lab, Role,
                        User)
from app.schemas import (IssueCommentOut, IssueDetail, IssueHistoryOut,
                         IssueOut, IssuePhotoOut)
from app.services.events import queue_message
from app.services.notifications import notify, staff_ids
from app.services.storage import (ImageRejected, get_storage, new_key,
                                  process_image)


class IssueError(Exception):
    """A request the rules refuse. `status` is the HTTP status to use."""

    def __init__(self, status: int, message: str, code: str = "INVALID"):
        self.status = status
        self.message = message
        self.code = code
        super().__init__(message)


ACTIVE = (IssueStatus.OPEN, IssueStatus.ACKNOWLEDGED, IssueStatus.IN_PROGRESS,
          IssueStatus.WAITING_FOR_PARTS)
FINISHED = (IssueStatus.RESOLVED, IssueStatus.CLOSED, IssueStatus.REJECTED)

# Transitions available through the general status endpoint. Resolving needs
# notes (it goes through resolve()), and closing/reopening are admin actions
# with their own endpoints.
STAFF_TRANSITIONS: dict[IssueStatus, tuple[IssueStatus, ...]] = {
    IssueStatus.OPEN: (IssueStatus.ACKNOWLEDGED, IssueStatus.IN_PROGRESS,
                       IssueStatus.WAITING_FOR_PARTS, IssueStatus.REJECTED),
    IssueStatus.ACKNOWLEDGED: (IssueStatus.IN_PROGRESS,
                               IssueStatus.WAITING_FOR_PARTS,
                               IssueStatus.REJECTED),
    IssueStatus.IN_PROGRESS: (IssueStatus.WAITING_FOR_PARTS,),
    IssueStatus.WAITING_FOR_PARTS: (IssueStatus.IN_PROGRESS,),
}

SEVERITY_RANK = {IssueSeverity.LOW: 0, IssueSeverity.MEDIUM: 1,
                 IssueSeverity.HIGH: 2, IssueSeverity.CRITICAL: 3}

STATUS_LABEL = {
    IssueStatus.OPEN: "Open", IssueStatus.ACKNOWLEDGED: "Acknowledged",
    IssueStatus.IN_PROGRESS: "In progress",
    IssueStatus.WAITING_FOR_PARTS: "Waiting for parts",
    IssueStatus.RESOLVED: "Resolved", IssueStatus.CLOSED: "Closed",
    IssueStatus.REJECTED: "Rejected",
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _utc(dt: datetime) -> datetime:
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None \
        else dt.astimezone(timezone.utc)


def is_staff(user: User) -> bool:
    return user.role in (Role.ADMIN, Role.LAB_STAFF)


def sla_hours() -> dict[str, int]:
    return {
        IssueSeverity.CRITICAL.value: settings.ISSUE_SLA_HOURS_CRITICAL,
        IssueSeverity.HIGH.value: settings.ISSUE_SLA_HOURS_HIGH,
        IssueSeverity.MEDIUM.value: settings.ISSUE_SLA_HOURS_MEDIUM,
        IssueSeverity.LOW.value: settings.ISSUE_SLA_HOURS_LOW,
    }


def is_overdue(issue: Issue, now: Optional[datetime] = None) -> bool:
    if issue.status not in ACTIVE:
        return False
    now = now or _now()
    limit = timedelta(hours=sla_hours()[issue.severity.value])
    return _utc(issue.created_at) + limit < now


# ---------------------------------------------------------------------------
# Access
# ---------------------------------------------------------------------------
def get_visible(db: Session, issue_id: int, user: User) -> Issue:
    """
    404, never 403, for an issue the caller may not see: confirming that
    somebody else's report exists is itself information.
    """
    issue = db.get(Issue, issue_id)
    if issue is None or (not is_staff(user) and issue.reporter_id != user.id):
        raise IssueError(404, "Issue not found", "NOT_FOUND")
    return issue


def _require_staff(user: User) -> None:
    if not is_staff(user):
        raise IssueError(403, "Only laboratory staff can do this.", "FORBIDDEN")


def _require_admin(user: User) -> None:
    if user.role != Role.ADMIN:
        raise IssueError(403, "Only an administrator can do this.", "FORBIDDEN")


def _history(db: Session, issue: Issue, actor: Optional[User],
             event_type: IssueEventType, message: str = "", *,
             old: Optional[IssueStatus] = None,
             new: Optional[IssueStatus] = None,
             detail: Optional[dict] = None,
             internal: bool = False) -> None:
    db.add(IssueHistory(issue_id=issue.id,
                        actor_id=actor.id if actor else None,
                        event_type=event_type, old_status=old, new_status=new,
                        message=message[:500], detail=detail,
                        is_internal=internal, created_at=_now()))
    issue.updated_at = _now()
    # Lets open staff views refresh without polling.
    queue_message(db, {"type": "staff", "kind": "issue", "issue_id": issue.id,
                       "event": event_type.value})


def _link(issue: Issue) -> str:
    return f"/issues/{issue.id}"


def _label(issue: Issue) -> str:
    return issue.ticket_number or f"Issue #{issue.id}"


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------
def create_issue(db: Session, reporter: User, *, lab_id: int,
                 asset_id: Optional[int], device_id: Optional[int],
                 access_event_id: Optional[int], category, severity,
                 title: str, description: str,
                 additional_comments: str = "") -> Issue:
    lab = db.get(Lab, lab_id)
    if lab is None:
        raise IssueError(422, "That laboratory does not exist.", "LAB_UNKNOWN")

    asset = _asset_in_lab(db, asset_id, lab) if asset_id else None
    device = _device_in_lab(db, device_id, lab) if device_id else None

    if access_event_id is not None:
        ev = db.get(AccessEvent, access_event_id)
        if ev is None or ev.lab_id != lab.id:
            raise IssueError(422, "That access event does not belong to this "
                                  "laboratory.", "EVENT_MISMATCH")
        # A student may point at their own door attempt, not anyone else's.
        if not is_staff(reporter) and ev.user_id != reporter.id:
            raise IssueError(422, "You can only link your own access events.",
                             "EVENT_MISMATCH")

    issue = Issue(reporter_id=reporter.id, lab_id=lab.id,
                  asset_id=asset.id if asset else None,
                  device_id=device.id if device else None,
                  access_event_id=access_event_id,
                  category=category, severity=severity, title=title,
                  description=description,
                  additional_comments=additional_comments,
                  status=IssueStatus.OPEN, created_at=_now(),
                  updated_at=_now())
    db.add(issue)
    db.flush()
    issue.ticket_number = f"ISS-{_utc(issue.created_at).year}-{issue.id:06d}"

    what = asset.name if asset else (device.name if device else lab.name)
    _history(db, issue, reporter, IssueEventType.ISSUE_CREATED,
             f"Reported by {reporter.full_name}", new=IssueStatus.OPEN,
             detail={"severity": severity.value, "category": category.value})

    critical = severity == IssueSeverity.CRITICAL
    notify(db, staff_ids(db),
           "ISSUE_CRITICAL" if critical else "ISSUE_REPORTED",
           f"{'CRITICAL: ' if critical else ''}{issue.ticket_number} - {title}",
           body=f"{lab.code} · {what} · {severity.value.title()} severity",
           link=_link(issue), severity="critical" if critical else
           ("warning" if severity == IssueSeverity.HIGH else "info"),
           issue_id=issue.id, exclude=reporter.id)
    db.commit()
    db.refresh(issue)
    return issue


def _asset_in_lab(db: Session, asset_id: int, lab: Lab) -> Asset:
    asset = db.get(Asset, asset_id)
    if asset is None or asset.lab_id != lab.id:
        raise IssueError(422, "That equipment is not registered in this "
                              "laboratory.", "ASSET_LAB_MISMATCH")
    return asset


def _device_in_lab(db: Session, device_id: int, lab: Lab) -> Device:
    device = db.get(Device, device_id)
    if device is None or device.lab_id != lab.id:
        raise IssueError(422, "That device is not installed in this "
                              "laboratory.", "DEVICE_LAB_MISMATCH")
    return device


# ---------------------------------------------------------------------------
# Staff workflow
# ---------------------------------------------------------------------------
def acknowledge(db: Session, issue: Issue, actor: User) -> Issue:
    _require_staff(actor)
    if issue.status != IssueStatus.OPEN:
        raise IssueError(409, f"Only open issues can be acknowledged; this one "
                              f"is {STATUS_LABEL[issue.status].lower()}.",
                         "BAD_TRANSITION")
    _set_status(db, issue, actor, IssueStatus.ACKNOWLEDGED,
                IssueEventType.ISSUE_ACKNOWLEDGED,
                f"Acknowledged by {actor.full_name}")
    notify(db, [issue.reporter_id], "ISSUE_ACKNOWLEDGED",
           f"{_label(issue)} acknowledged",
           body=f"Laboratory staff have seen your report \"{issue.title}\".",
           link=_link(issue), issue_id=issue.id, exclude=actor.id)
    db.commit()
    return issue


def assign(db: Session, issue: Issue, actor: User,
           assignee_id: Optional[int]) -> Issue:
    _require_staff(actor)
    if issue.status in FINISHED:
        raise IssueError(409, "A finished issue cannot be reassigned.",
                         "BAD_TRANSITION")
    assignee = None
    if assignee_id is not None:
        assignee = db.get(User, assignee_id)
        if assignee is None or not assignee.is_active or not is_staff(assignee):
            raise IssueError(422, "Issues can only be assigned to active "
                                  "laboratory staff.", "BAD_ASSIGNEE")
    previous = issue.assigned_to_id
    if previous == (assignee.id if assignee else None):
        return issue
    issue.assigned_to_id = assignee.id if assignee else None

    # Assigning an unread report is also acknowledging it.
    if assignee is not None and issue.status == IssueStatus.OPEN:
        _set_status(db, issue, actor, IssueStatus.ACKNOWLEDGED,
                    IssueEventType.ISSUE_ACKNOWLEDGED,
                    f"Acknowledged by {actor.full_name}")

    _history(db, issue, actor, IssueEventType.ISSUE_ASSIGNED,
             f"Assigned to {assignee.full_name}" if assignee else "Unassigned",
             detail={"from": previous,
                     "to": assignee.id if assignee else None})
    if assignee is not None:
        notify(db, [assignee.id], "ISSUE_ASSIGNED",
               f"{_label(issue)} assigned to you",
               body=f"{issue.title} ({issue.severity.value.title()})",
               link=_link(issue), issue_id=issue.id,
               severity="warning" if SEVERITY_RANK[issue.severity] >= 2 else "info",
               exclude=actor.id)
        notify(db, [issue.reporter_id], "ISSUE_ASSIGNED",
               f"{_label(issue)} assigned to {assignee.full_name}",
               body="A member of staff is now responsible for your report.",
               link=_link(issue), issue_id=issue.id, exclude=actor.id)
    db.commit()
    return issue


def change_status(db: Session, issue: Issue, actor: User,
                  new_status: IssueStatus, note: str = "") -> Issue:
    _require_staff(actor)
    if new_status == IssueStatus.RESOLVED:
        return resolve(db, issue, actor, note)
    if new_status == IssueStatus.CLOSED:
        return close(db, issue, actor, note)
    allowed = STAFF_TRANSITIONS.get(issue.status, ())
    if new_status not in allowed:
        raise IssueError(409, f"An issue that is "
                              f"{STATUS_LABEL[issue.status].lower()} cannot "
                              f"move to {STATUS_LABEL[new_status].lower()}.",
                         "BAD_TRANSITION")
    event = (IssueEventType.ISSUE_ACKNOWLEDGED
             if new_status == IssueStatus.ACKNOWLEDGED
             else IssueEventType.ISSUE_STATUS_CHANGED)
    msg = f"{STATUS_LABEL[issue.status]} → {STATUS_LABEL[new_status]}"
    if note:
        msg += f": {note}"
    _set_status(db, issue, actor, new_status, event, msg)
    notify(db, [issue.reporter_id], "ISSUE_STATUS",
           f"{_label(issue)} is now {STATUS_LABEL[new_status].lower()}",
           body=note or issue.title, link=_link(issue), issue_id=issue.id,
           exclude=actor.id)
    db.commit()
    return issue


def resolve(db: Session, issue: Issue, actor: User, notes: str) -> Issue:
    _require_staff(actor)
    notes = (notes or "").strip()
    if len(notes) < 5:
        raise IssueError(422, "Describe what was done to resolve the issue.",
                         "NOTES_REQUIRED")
    if issue.status not in ACTIVE:
        raise IssueError(409, f"This issue is already "
                              f"{STATUS_LABEL[issue.status].lower()}.",
                         "BAD_TRANSITION")
    issue.resolution_notes = notes
    issue.resolved_at = _now()
    _set_status(db, issue, actor, IssueStatus.RESOLVED,
                IssueEventType.ISSUE_RESOLVED,
                f"Resolved by {actor.full_name}: {notes}")
    notify(db, [issue.reporter_id], "ISSUE_RESOLVED",
           f"{_label(issue)} resolved",
           body=notes, link=_link(issue), issue_id=issue.id, exclude=actor.id)
    db.commit()
    return issue


def close(db: Session, issue: Issue, actor: User, note: str = "") -> Issue:
    _require_admin(actor)
    if issue.status not in (IssueStatus.RESOLVED, IssueStatus.REJECTED):
        raise IssueError(409, "Only resolved or rejected issues can be closed.",
                         "BAD_TRANSITION")
    issue.closed_at = _now()
    _set_status(db, issue, actor, IssueStatus.CLOSED,
                IssueEventType.ISSUE_CLOSED,
                f"Closed by {actor.full_name}" + (f": {note}" if note else ""))
    notify(db, [issue.reporter_id], "ISSUE_CLOSED",
           f"{_label(issue)} closed", body=note or issue.title,
           link=_link(issue), issue_id=issue.id, exclude=actor.id)
    db.commit()
    return issue


def reopen(db: Session, issue: Issue, actor: User, note: str = "") -> Issue:
    _require_admin(actor)
    if issue.status not in FINISHED:
        raise IssueError(409, "Only resolved, rejected or closed issues can be "
                              "reopened.", "BAD_TRANSITION")
    issue.resolved_at = None
    issue.closed_at = None
    _set_status(db, issue, actor, IssueStatus.OPEN,
                IssueEventType.ISSUE_REOPENED,
                f"Reopened by {actor.full_name}" + (f": {note}" if note else ""))
    notify(db, [issue.reporter_id] + ([issue.assigned_to_id]
                                      if issue.assigned_to_id else []),
           "ISSUE_REOPENED", f"{_label(issue)} reopened",
           body=note or issue.title, link=_link(issue), issue_id=issue.id,
           exclude=actor.id)
    db.commit()
    return issue


def update(db: Session, issue: Issue, actor: User, changes: dict) -> Issue:
    _require_staff(actor)
    lab = db.get(Lab, issue.lab_id)
    detail: dict = {}

    if "severity" in changes and changes["severity"] is not None \
            and changes["severity"] != issue.severity:
        old, new = issue.severity, changes["severity"]
        issue.severity = new
        _history(db, issue, actor, IssueEventType.ISSUE_SEVERITY_CHANGED,
                 f"Severity {old.value.title()} → {new.value.title()}",
                 detail={"from": old.value, "to": new.value})
        # Escalation into HIGH or CRITICAL is something the whole team hears.
        if SEVERITY_RANK[new] > SEVERITY_RANK[old] and SEVERITY_RANK[new] >= 2:
            notify(db, staff_ids(db), "ISSUE_ESCALATED",
                   f"{_label(issue)} escalated to {new.value.title()}",
                   body=issue.title, link=_link(issue), issue_id=issue.id,
                   severity="critical" if new == IssueSeverity.CRITICAL
                   else "warning", exclude=actor.id)

    if changes.get("category") is not None and changes["category"] != issue.category:
        detail["category"] = [issue.category.value, changes["category"].value]
        issue.category = changes["category"]
    if "asset_id" in changes:
        aid = changes["asset_id"]
        if aid is not None:
            _asset_in_lab(db, aid, lab)
        if aid != issue.asset_id:
            detail["asset_id"] = [issue.asset_id, aid]
            issue.asset_id = aid
    if "device_id" in changes:
        did = changes["device_id"]
        if did is not None:
            _device_in_lab(db, did, lab)
        if did != issue.device_id:
            detail["device_id"] = [issue.device_id, did]
            issue.device_id = did
    if changes.get("title"):
        t = changes["title"].strip()
        if len(t) < 5:
            raise IssueError(422, "Title must be at least 5 characters.")
        if t != issue.title:
            detail["title"] = [issue.title, t]
            issue.title = t
    if changes.get("resolution_notes") is not None:
        issue.resolution_notes = changes["resolution_notes"].strip()
        detail["resolution_notes"] = "updated"

    if detail:
        _history(db, issue, actor, IssueEventType.ISSUE_UPDATED,
                 "Updated " + ", ".join(k.replace("_id", "").replace("_", " ")
                                        for k in detail), detail=detail)
    db.commit()
    return issue


def _set_status(db: Session, issue: Issue, actor: User, new: IssueStatus,
                event: IssueEventType, message: str) -> None:
    old = issue.status
    issue.status = new
    if new == IssueStatus.ACKNOWLEDGED and issue.acknowledged_at is None:
        issue.acknowledged_at = _now()
    _history(db, issue, actor, event, message, old=old, new=new)


# ---------------------------------------------------------------------------
# Comments and photos
# ---------------------------------------------------------------------------
def can_comment(issue: Issue, user: User) -> bool:
    if is_staff(user):
        return issue.status != IssueStatus.CLOSED
    return issue.reporter_id == user.id and issue.status in ACTIVE


def can_add_photos(issue: Issue, user: User) -> bool:
    return can_comment(issue, user)


def add_comment(db: Session, issue: Issue, author: User, body: str,
                internal: bool) -> IssueComment:
    if not can_comment(issue, author):
        raise IssueError(403 if not is_staff(author) else 409,
                         "Comments are closed for this issue.",
                         "COMMENTS_CLOSED")
    if internal and not is_staff(author):
        raise IssueError(403, "Only staff can add internal notes.", "FORBIDDEN")
    c = IssueComment(issue_id=issue.id, author_id=author.id, body=body,
                     is_internal=internal, created_at=_now())
    db.add(c)
    _history(db, issue, author, IssueEventType.ISSUE_COMMENT_ADDED,
             ("Internal note by " if internal else "Comment by ")
             + author.full_name, internal=internal)
    if not internal:
        if is_staff(author):
            notify(db, [issue.reporter_id], "ISSUE_COMMENT",
                   f"New update on {_label(issue)}", body=body[:200],
                   link=_link(issue), issue_id=issue.id, exclude=author.id)
        else:
            to = [issue.assigned_to_id] if issue.assigned_to_id else staff_ids(db)
            notify(db, to, "ISSUE_COMMENT",
                   f"{author.full_name} added information to {_label(issue)}",
                   body=body[:200], link=_link(issue), issue_id=issue.id,
                   exclude=author.id)
    db.commit()
    db.refresh(c)
    return c


def add_photos(db: Session, issue: Issue, uploader: User,
               files: list[tuple[str, bytes]],
               stage: IssuePhotoStage) -> list[IssuePhoto]:
    """
    All-or-nothing: every file is validated and processed before any is
    stored, so a batch with one bad file leaves nothing half-uploaded.
    """
    if not can_add_photos(issue, uploader):
        raise IssueError(403 if not is_staff(uploader) else 409,
                         "Photos can no longer be added to this issue.",
                         "PHOTOS_CLOSED")
    if not is_staff(uploader) and stage != IssuePhotoStage.REPORT:
        raise IssueError(403, "Only staff can add maintenance photos.",
                         "FORBIDDEN")
    if not files:
        raise IssueError(422, "No files were uploaded.", "NO_FILES")
    if len(files) > settings.MAX_PHOTOS_PER_REQUEST:
        raise IssueError(422, f"Upload at most {settings.MAX_PHOTOS_PER_REQUEST} "
                              f"photos at a time.", "TOO_MANY_FILES")
    existing = len(issue.photos)
    if existing + len(files) > settings.MAX_PHOTOS_PER_ISSUE:
        raise IssueError(422, f"An issue can hold at most "
                              f"{settings.MAX_PHOTOS_PER_ISSUE} photos "
                              f"({existing} already attached).",
                         "TOO_MANY_FILES")

    processed = []
    errors = []
    for name, raw in files:
        try:
            processed.append((name, process_image(raw)))
        except ImageRejected as e:
            errors.append(f"{name or 'file'}: {e}")
    if errors:
        raise IssueError(422, " ".join(errors), "INVALID_IMAGE")

    storage = get_storage()
    stored: list[str] = []
    rows: list[IssuePhoto] = []
    try:
        for name, img in processed:
            key, thumb_key = new_key(f"issues/{issue.id}", img.ext)
            storage.put(key, img.data, img.content_type)
            stored.append(key)
            storage.put(thumb_key, img.thumb, img.content_type)
            stored.append(thumb_key)
            row = IssuePhoto(issue_id=issue.id, uploaded_by_id=uploader.id,
                             stage=stage, storage_key=key, thumb_key=thumb_key,
                             original_filename=(name or "")[:255],
                             content_type=img.content_type,
                             size_bytes=len(img.data), width=img.width,
                             height=img.height, created_at=_now())
            db.add(row)
            rows.append(row)
        n = len(rows)
        stage_txt = "" if stage == IssuePhotoStage.REPORT \
            else f" ({stage.value.lower()} maintenance)"
        _history(db, issue, uploader, IssueEventType.ISSUE_PHOTO_ADDED,
                 f"{n} photo{'s' if n != 1 else ''} added{stage_txt} by "
                 f"{uploader.full_name}", detail={"stage": stage.value,
                                                  "count": n})
        db.commit()
    except Exception:
        db.rollback()
        for key in stored:          # no orphaned files for a failed batch
            storage.delete(key)
        raise
    for r in rows:
        db.refresh(r)
    return rows


# ---------------------------------------------------------------------------
# Serialisation
# ---------------------------------------------------------------------------
def to_out(db: Session, issue: Issue, now: Optional[datetime] = None) -> IssueOut:
    out = IssueOut.model_validate(issue)
    lab = db.get(Lab, issue.lab_id)
    out.lab_code = lab.code if lab else None
    out.lab_name = lab.name if lab else None
    if issue.asset_id:
        a = db.get(Asset, issue.asset_id)
        out.asset_tag = a.asset_tag if a else None
        out.asset_name = a.name if a else None
    if issue.device_id:
        d = db.get(Device, issue.device_id)
        out.device_name = d.name if d else None
    rep = db.get(User, issue.reporter_id)
    out.reporter_name = rep.full_name if rep else None
    if issue.assigned_to_id:
        asg = db.get(User, issue.assigned_to_id)
        out.assignee_name = asg.full_name if asg else None
    out.photo_count = len(issue.photos)
    out.is_overdue = is_overdue(issue, now)
    return out


def to_detail(db: Session, issue: Issue, viewer: User) -> IssueDetail:
    base = to_out(db, issue)
    staff = is_staff(viewer)
    names: dict[int, User | None] = {}

    def person(uid: Optional[int]) -> Optional[User]:
        if uid is None:
            return None
        if uid not in names:
            names[uid] = db.get(User, uid)
        return names[uid]

    photos = []
    for p in issue.photos:
        po = IssuePhotoOut.model_validate(p)
        u = person(p.uploaded_by_id)
        po.uploaded_by_name = u.full_name if u else None
        photos.append(po)

    comments = []
    for c in issue.comments:
        if c.is_internal and not staff:
            continue
        co = IssueCommentOut.model_validate(c)
        u = person(c.author_id)
        co.author_name = u.full_name if u else None
        co.author_role = u.role if u else None
        comments.append(co)

    history = []
    for h in issue.history:
        if h.is_internal and not staff:
            continue
        ho = IssueHistoryOut.model_validate(h)
        u = person(h.actor_id)
        ho.actor_name = u.full_name if u else None
        ho.actor_role = u.role if u else None
        history.append(ho)

    allowed: list[IssueStatus] = []
    if staff:
        allowed = list(STAFF_TRANSITIONS.get(issue.status, ()))
        if issue.status in ACTIVE:
            allowed.append(IssueStatus.RESOLVED)
        if viewer.role == Role.ADMIN and issue.status in (
                IssueStatus.RESOLVED, IssueStatus.REJECTED):
            allowed.append(IssueStatus.CLOSED)

    return IssueDetail(
        **base.model_dump(), photos=photos, comments=comments, history=history,
        can_manage=staff, can_close=viewer.role == Role.ADMIN,
        can_comment=can_comment(issue, viewer),
        can_add_photos=can_add_photos(issue, viewer),
        allowed_statuses=allowed)


# ---------------------------------------------------------------------------
# Aggregates
# ---------------------------------------------------------------------------
def summary(db: Session, lab_id: Optional[int] = None) -> dict:
    now = _now()
    stmt = select(Issue)
    if lab_id is not None:
        stmt = stmt.where(Issue.lab_id == lab_id)
    issues = db.scalars(stmt).all()
    active = [i for i in issues if i.status in ACTIVE]
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    resolved_durations = [
        (_utc(i.resolved_at) - _utc(i.created_at)).total_seconds() / 3600
        for i in issues if i.resolved_at is not None]

    labs = {l.id: l for l in db.scalars(select(Lab)).all()}
    assets = {a.id: a for a in db.scalars(select(Asset)).all()}

    by_lab = Counter(i.lab_id for i in active)
    by_cat = Counter(i.category.value for i in active)
    # Most frequently reported equipment: all time, not just open, because
    # a machine that keeps failing is the finding.
    by_asset = Counter(i.asset_id for i in issues if i.asset_id)
    by_status = Counter(i.status.value for i in issues)

    days = 30
    start = (now - timedelta(days=days - 1)).date()
    created = Counter(_utc(i.created_at).date() for i in issues
                      if _utc(i.created_at).date() >= start)
    resolved = Counter(_utc(i.resolved_at).date() for i in issues
                       if i.resolved_at and _utc(i.resolved_at).date() >= start)
    trend = []
    if issues:
        for k in range(days):
            d = start + timedelta(days=k)
            trend.append({"day": d.isoformat(), "created": created.get(d, 0),
                          "resolved": resolved.get(d, 0)})

    return {
        "open": len(active),
        "critical": sum(1 for i in active if i.severity == IssueSeverity.CRITICAL),
        "high": sum(1 for i in active if i.severity == IssueSeverity.HIGH),
        "in_progress": sum(1 for i in active if i.status == IssueStatus.IN_PROGRESS),
        "waiting_for_parts": sum(1 for i in active
                                 if i.status == IssueStatus.WAITING_FOR_PARTS),
        "unassigned": sum(1 for i in active if i.assigned_to_id is None),
        "overdue": sum(1 for i in active if is_overdue(i, now)),
        "resolved_this_month": sum(1 for i in issues if i.resolved_at
                                   and _utc(i.resolved_at) >= month_start),
        "total": len(issues),
        "avg_resolution_hours": (round(sum(resolved_durations)
                                       / len(resolved_durations), 1)
                                 if resolved_durations else None),
        "by_lab": [{"key": str(k), "label": labs[k].code if k in labs else str(k),
                    "count": n} for k, n in by_lab.most_common()],
        "by_category": [{"key": k, "label": k.replace("_", " ").title(),
                         "count": n} for k, n in by_cat.most_common()],
        "by_asset": [{"key": str(k),
                      "label": assets[k].name if k in assets else str(k),
                      "count": n} for k, n in by_asset.most_common(8)],
        "by_status": [{"key": k, "label": STATUS_LABEL[IssueStatus(k)],
                       "count": n} for k, n in by_status.most_common()],
        "trend": trend,
        "sla_hours": sla_hours(),
    }
