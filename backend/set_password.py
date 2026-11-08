"""
Set a portal account's password from the laptop (2026-10-27) - the recovery path when nobody can sign in as an
administrator, and the way to replace the initial passwords. The password is typed twice at a hidden prompt: it is
never a command-line argument (no shell history, no process list) and never printed or logged.

    docker compose exec backend python set_password.py admin@giu-uni.de

The same password rules as the portal's Users & roles page apply. The change is written to the audit log.
"""
from __future__ import annotations

import getpass
import sys
from typing import Callable, Optional


def main(argv: list[str], ask: Callable[[str], str] = getpass.getpass, db=None) -> int:
    from sqlalchemy import select

    from app.core import password_policy
    from app.core.security import hash_password
    from app.models import AuditLog, User
    if len(argv) != 1 or "@" not in argv[0]:
        print("usage: python set_password.py <email>")
        return 2
    own = db is None
    if own:
        from app.db.session import SessionLocal
        db = SessionLocal()
    try:
        u = db.scalar(select(User).where(User.email == argv[0].strip().lower()))
        if u is None:
            print("No such account.")
            return 1
        pw = ask(f"New password for {u.email}: ")
        if pw != ask("Again: "):
            print("The two entries differ - nothing changed.")
            return 1
        bad = password_policy.problems(pw, u.email, u.full_name)
        if bad:
            print("Not accepted: " + "; ".join(bad))
            return 1
        u.hashed_password = hash_password(pw)
        db.add(AuditLog(actor_user_id=None, action="PASSWORD_SET_LOCALLY", entity_type="user", entity_id=str(u.id),
                        detail={"via": "set_password.py"}))
        db.commit()
        print(f"Password changed for {u.email}.")
        return 0
    finally:
        if own:
            db.close()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
