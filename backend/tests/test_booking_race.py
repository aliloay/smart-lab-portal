"""Two bookings for the same lab and time, sent at the same moment: exactly one is saved (2026-10-26 audit).
The overlap check is slowed down on purpose so the two requests are both inside it at once - without the per-lab
lock both passed and both were saved."""
import threading
import time
from datetime import datetime, timedelta, timezone

from app.db.session import SessionLocal
from app.models import Booking, BookingStatus, Lab, User
from app.services import booking as svc


def test_simultaneous_overlapping_bookings_only_one_wins(db, alice, bob, lab, monkeypatch):
    real = svc.find_conflicts

    def slow(*a, **k):
        r = real(*a, **k)
        time.sleep(0.4)                              # both requests are now past the check
        return r
    monkeypatch.setattr(svc, "find_conflicts", slow)
    start = datetime.now(timezone.utc).replace(microsecond=0) + timedelta(days=2)
    go, results = threading.Barrier(2), {}

    def book(uid, offset_min):
        s = SessionLocal()
        try:
            u, l = s.get(User, uid), s.get(Lab, lab.id)
            go.wait()
            svc.create_booking(s, u, l, start + timedelta(minutes=offset_min),
                               start + timedelta(minutes=offset_min + 60), "race")
            results[uid] = "OK"
        except svc.BookingError as e:
            results[uid] = e.code
        finally:
            s.close()
    ts = [threading.Thread(target=book, args=(alice.id, 0)), threading.Thread(target=book, args=(bob.id, 30))]
    [t.start() for t in ts]; [t.join(10) for t in ts]
    assert sorted(results.values()) == ["CONFLICT", "OK"], results
    db.expire_all()
    live = db.query(Booking).filter(Booking.lab_id == lab.id,
                                    Booking.status.in_([BookingStatus.PENDING, BookingStatus.CONFIRMED])).count()
    assert live == 1
