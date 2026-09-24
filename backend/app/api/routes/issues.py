"""
Issue reporting and maintenance.

Thin by design: every permission and transition rule lives in
app.services.issues. A student listing issues is narrowed to their own
server-side, whatever the query string asks for.
"""
from typing import Optional

from fastapi import (APIRouter, Depends, File, Form, HTTPException, Query,
                     UploadFile, status)
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import StreamingResponse
from sqlalchemy import desc, or_, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_staff
from app.core.config import settings
from app.db.session import get_db
from app.models import (Issue, IssueCategory, IssuePhoto, IssuePhotoStage,
                        IssueSeverity, IssueStatus, User)
from app.schemas import (CommentCreate, IssueAssign, IssueCommentOut,
                         IssueCreate, IssueDetail, IssueOut, IssuePhotoOut,
                         IssueResolve, IssueStatusChange, IssueSummary,
                         IssueUpdate, NoteBody)
from app.services import issues as svc
from app.services.storage import get_storage

router = APIRouter(prefix="/issues", tags=["issues"])


def _raise(e: svc.IssueError):
    raise HTTPException(e.status, detail={"code": e.code, "message": e.message})


def _visible(db: Session, issue_id: int, user: User) -> Issue:
    try:
        return svc.get_visible(db, issue_id, user)
    except svc.IssueError as e:
        _raise(e)


@router.post("", response_model=IssueDetail, status_code=status.HTTP_201_CREATED)
def create_issue(req: IssueCreate, db: Session = Depends(get_db),
                 user: User = Depends(get_current_user)):
    try:
        issue = svc.create_issue(db, user, **req.model_dump())
    except svc.IssueError as e:
        _raise(e)
    return svc.to_detail(db, issue, user)


@router.get("", response_model=list[IssueOut])
def list_issues(
    status_: Optional[list[IssueStatus]] = Query(None, alias="status"),
    severity: Optional[list[IssueSeverity]] = Query(None),
    category: Optional[IssueCategory] = None,
    lab_id: Optional[int] = None,
    asset_id: Optional[int] = None,
    assigned: Optional[str] = Query(None, description="'me', 'unassigned' or a user id"),
    mine: bool = False,
    active: Optional[bool] = None,
    overdue: bool = False,
    q: Optional[str] = Query(None, max_length=100),
    limit: int = Query(200, le=500),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    stmt = select(Issue).order_by(desc(Issue.created_at))
    # A student's list is their own reports, full stop.
    if not svc.is_staff(user) or mine:
        stmt = stmt.where(Issue.reporter_id == user.id)
    if status_:
        stmt = stmt.where(Issue.status.in_(status_))
    if active is True:
        stmt = stmt.where(Issue.status.in_(svc.ACTIVE))
    elif active is False:
        stmt = stmt.where(Issue.status.in_(svc.FINISHED))
    if severity:
        stmt = stmt.where(Issue.severity.in_(severity))
    if category is not None:
        stmt = stmt.where(Issue.category == category)
    if lab_id is not None:
        stmt = stmt.where(Issue.lab_id == lab_id)
    if asset_id is not None:
        stmt = stmt.where(Issue.asset_id == asset_id)
    if assigned == "me":
        stmt = stmt.where(Issue.assigned_to_id == user.id)
    elif assigned == "unassigned":
        stmt = stmt.where(Issue.assigned_to_id.is_(None))
    elif assigned and assigned.isdigit():
        stmt = stmt.where(Issue.assigned_to_id == int(assigned))
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(or_(Issue.title.ilike(like),
                              Issue.description.ilike(like),
                              Issue.ticket_number.ilike(like)))
    rows = db.scalars(stmt.limit(limit)).all()
    out = [svc.to_out(db, i) for i in rows]
    if overdue:
        out = [i for i in out if i.is_overdue]
    return out


@router.get("/summary", response_model=IssueSummary)
def issue_summary(lab_id: Optional[int] = None, db: Session = Depends(get_db),
                  _: User = Depends(require_staff)):
    return svc.summary(db, lab_id)


@router.get("/{issue_id}", response_model=IssueDetail)
def get_issue(issue_id: int, db: Session = Depends(get_db),
              user: User = Depends(get_current_user)):
    return svc.to_detail(db, _visible(db, issue_id, user), user)


@router.patch("/{issue_id}", response_model=IssueDetail)
def update_issue(issue_id: int, req: IssueUpdate,
                 db: Session = Depends(get_db),
                 user: User = Depends(get_current_user)):
    issue = _visible(db, issue_id, user)
    try:
        svc.update(db, issue, user, req.model_dump(exclude_unset=True))
    except svc.IssueError as e:
        _raise(e)
    return svc.to_detail(db, issue, user)


def _action(fn):
    """Shared shape for the single-verb workflow endpoints."""
    def run(issue_id: int, db: Session, user: User, *args):
        issue = _visible(db, issue_id, user)
        try:
            fn(db, issue, user, *args)
        except svc.IssueError as e:
            _raise(e)
        db.refresh(issue)
        return svc.to_detail(db, issue, user)
    return run


@router.post("/{issue_id}/acknowledge", response_model=IssueDetail)
def acknowledge(issue_id: int, db: Session = Depends(get_db),
                user: User = Depends(get_current_user)):
    return _action(svc.acknowledge)(issue_id, db, user)


@router.post("/{issue_id}/assign", response_model=IssueDetail)
def assign(issue_id: int, req: IssueAssign, db: Session = Depends(get_db),
           user: User = Depends(get_current_user)):
    return _action(svc.assign)(issue_id, db, user, req.assignee_id)


@router.post("/{issue_id}/status", response_model=IssueDetail)
def change_status(issue_id: int, req: IssueStatusChange,
                  db: Session = Depends(get_db),
                  user: User = Depends(get_current_user)):
    return _action(svc.change_status)(issue_id, db, user, req.status, req.note)


@router.post("/{issue_id}/resolve", response_model=IssueDetail)
def resolve(issue_id: int, req: IssueResolve, db: Session = Depends(get_db),
            user: User = Depends(get_current_user)):
    return _action(svc.resolve)(issue_id, db, user, req.resolution_notes)


@router.post("/{issue_id}/close", response_model=IssueDetail)
def close(issue_id: int, req: Optional[NoteBody] = None,
          db: Session = Depends(get_db),
          user: User = Depends(get_current_user)):
    return _action(svc.close)(issue_id, db, user, req.note if req else "")


@router.post("/{issue_id}/reopen", response_model=IssueDetail)
def reopen(issue_id: int, req: Optional[NoteBody] = None,
           db: Session = Depends(get_db),
           user: User = Depends(get_current_user)):
    return _action(svc.reopen)(issue_id, db, user, req.note if req else "")


@router.post("/{issue_id}/comments", response_model=IssueCommentOut,
             status_code=status.HTTP_201_CREATED)
def add_comment(issue_id: int, req: CommentCreate,
                db: Session = Depends(get_db),
                user: User = Depends(get_current_user)):
    issue = _visible(db, issue_id, user)
    try:
        c = svc.add_comment(db, issue, user, req.body, req.is_internal)
    except svc.IssueError as e:
        _raise(e)
    out = IssueCommentOut.model_validate(c)
    out.author_name = user.full_name
    out.author_role = user.role
    return out


@router.post("/{issue_id}/photos", response_model=list[IssuePhotoOut],
             status_code=status.HTTP_201_CREATED)
async def upload_photos(issue_id: int,
                        files: list[UploadFile] = File(...),
                        stage: IssuePhotoStage = Form(IssuePhotoStage.REPORT),
                        db: Session = Depends(get_db),
                        user: User = Depends(get_current_user)):
    issue = _visible(db, issue_id, user)
    limit = settings.MAX_UPLOAD_MB * 1024 * 1024
    payload: list[tuple[str, bytes]] = []
    for f in files[: settings.MAX_PHOTOS_PER_REQUEST + 1]:
        # Read one byte past the limit: enough to know it is too big without
        # buffering an arbitrarily large body.
        raw = await f.read(limit + 1)
        payload.append((f.filename or "", raw))
    try:
        # Decoding and re-encoding images is CPU work; keep it off the loop.
        rows = await run_in_threadpool(svc.add_photos, db, issue, user,
                                       payload, stage)
    except svc.IssueError as e:
        _raise(e)
    out = []
    for r in rows:
        o = IssuePhotoOut.model_validate(r)
        o.uploaded_by_name = user.full_name
        out.append(o)
    return out


@router.get("/{issue_id}/photos", response_model=list[IssuePhotoOut])
def list_photos(issue_id: int, db: Session = Depends(get_db),
                user: User = Depends(get_current_user)):
    return svc.to_detail(db, _visible(db, issue_id, user), user).photos


@router.get("/{issue_id}/photos/{photo_id}/file")
def photo_file(issue_id: int, photo_id: int,
               variant: str = Query("full", pattern="^(full|thumb)$"),
               download: bool = False,
               db: Session = Depends(get_db),
               user: User = Depends(get_current_user)):
    """
    Streams the stored image. Authenticated like every other route: the
    photos can show the inside of a laboratory, so they are not public files.
    """
    issue = _visible(db, issue_id, user)
    photo = db.get(IssuePhoto, photo_id)
    if photo is None or photo.issue_id != issue.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Photo not found")
    key = photo.thumb_key if variant == "thumb" else photo.storage_key
    storage = get_storage()
    if not storage.exists(key):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Photo file missing")
    ext = key.rsplit(".", 1)[-1]
    base = (issue.ticket_number or f"issue-{issue.id}")
    name = f"{base}-photo-{photo.id}.{ext}"
    disposition = "attachment" if download else "inline"
    return StreamingResponse(
        storage.open(key), media_type=photo.content_type,
        headers={"Content-Disposition": f'{disposition}; filename="{name}"',
                 "Cache-Control": "private, max-age=3600",
                 "X-Content-Type-Options": "nosniff"})
