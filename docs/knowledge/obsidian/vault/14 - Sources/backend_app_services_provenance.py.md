---
type: "source-mirror"
source_kind: "source-code"
source_path: "backend/app/services/provenance.py"
source_hash: "cf317db9d14eacf4f662255610e346f1fe8fd66905cede2edb73344b621fb571"
generated: true
updated: "2026-11-04T00:02:39+02:00"
---
> Read-only mirror of `backend/app/services/provenance.py` - edit the original in the repository, not this note.

Systems: none

## Related
- [[backend_app_api_routes_experiments.py]] - imports
- [[backend_app_api_routes_system.py]] - imports
- [[backend_app_core_config.py]] - imports
- [[backend_app_models___init__.py]] - imports
- [[backend_app_models_tables.py]] - imports

```py
"""
Data provenance: every event, reading, alert, booking, session, ticket and
camera event says where it came from (models.PROVENANCES).

  * New rows are stamped when they are written: the RUNNING experiment's
    data_mode and id if one is running, else the system data mode
    (Settings, admin only; default settings.DATA_MODE_DEFAULT).
  * A row's provenance never changes afterwards: changing the data mode
    affects new rows only, and the application refuses to rewrite the
    provenance of an existing row (ProvenanceImmutable). History that cannot
    be proven stays UNKNOWN_PROVENANCE; nothing is deleted.

Thesis queries filter on provenance (and experiment_id); operational views
show everything.
"""
from __future__ import annotations

import time
from typing import Optional

from sqlalchemy import event, inspect, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import PROVENANCES, Experiment, SystemSetting
from app.models.tables import ProvenanceMixin

MODE_KEY = "data_mode"
ACTIVE_KEY = "active_experiment_id"
_CACHE_S = 2.0
_cache: dict[str, tuple[float, str, Optional[int]]] = {}


class ProvenanceImmutable(RuntimeError):
    pass


def invalidate() -> None:
    _cache.clear()


def current(session: Session) -> tuple[str, Optional[int]]:
    """(provenance, experiment_id) for a row written now."""
    key = str(session.get_bind().url)
    hit = _cache.get(key)
    if hit and time.monotonic() - hit[0] < _CACHE_S:
        return hit[1], hit[2]
    with session.no_autoflush:
        rows = dict(session.execute(select(SystemSetting.key, SystemSetting.value).where(
            SystemSetting.key.in_([MODE_KEY, ACTIVE_KEY]))).all())
        mode, exp_id = rows.get(MODE_KEY) or settings.DATA_MODE_DEFAULT, None
        if rows.get(ACTIVE_KEY):
            exp = session.get(Experiment, int(rows[ACTIVE_KEY]))
            if exp is not None and exp.status == "RUNNING":
                mode, exp_id = exp.data_mode, exp.id
    if mode not in PROVENANCES:
        mode = "UNKNOWN_PROVENANCE"
    _cache[key] = (time.monotonic(), mode, exp_id)
    return mode, exp_id


def set_setting(session: Session, key: str, value: str) -> None:
    from app.models import utcnow
    row = session.get(SystemSetting, key)
    if row is None:
        session.add(SystemSetting(key=key, value=value, updated_at=utcnow()))
    else:
        row.value, row.updated_at = value, utcnow()
    invalidate()


@event.listens_for(Session, "before_flush")
def _stamp(session: Session, _ctx, _instances) -> None:
    new = [o for o in session.new if isinstance(o, ProvenanceMixin) and o.provenance is None]
    if new:
        mode, exp_id = current(session)
        for o in new:
            o.provenance = mode
            if o.experiment_id is None:
                o.experiment_id = exp_id
    for o in session.dirty:
        if isinstance(o, ProvenanceMixin):
            h = inspect(o).attrs.provenance.history
            if h.deleted and h.deleted[0] is not None and h.added and h.added[0] != h.deleted[0]:
                raise ProvenanceImmutable(
                    f"{type(o).__name__} {o.id}: provenance is set once and never rewritten")

```
