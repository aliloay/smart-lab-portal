"""
What the AI assistants know about how Smart Lab works.

Plain-language flow of the whole system, so the chat can answer "why isn't my
QR code working?" or "how do I register my face?" as well as data questions.
Deliberately free of secrets, network addresses, keys and internal endpoints:
it describes what people see and do, not how to reach or bypass anything.
Kept short because small local models have a small context window.
"""
from app.core.config import settings
from app.ui_text import _DENIAL


def guide() -> str:
    grace = settings.BOOKING_GRACE_MINUTES
    window = ("from the booking's start time until its end time" if not grace else
              f"from {grace} min before the booking starts until {grace} min after it ends")
    approve = ("confirmed immediately" if settings.BOOKING_AUTO_APPROVE else
               "confirmed after staff approve them (they show as Pending until then)")
    reasons = "\n".join(f"  - {k}: {v}" for k, v in _DENIAL.items())
    return f"""HOW SMART LAB WORKS (German International University, Cairo)

Roles: students book labs and report problems; lab staff run the labs and fix
issues; administrators manage accounts, devices and settings.

Booking: "Book a lab" / "New booking" -> choose a lab, day and time (at most
{settings.MAX_BOOKING_HOURS} h). Bookings are {approve}. Cancel or show the QR
code under "My bookings". A reminder arrives {settings.BOOKING_REMINDER_MINUTES}
min before the start. Only LAB_01 has an automatic door today; the other labs
are booked in the portal but have no electronic lock.

Entering a lab (two steps, both needed, same person):
  1. Step 1 - show your booking QR code (My bookings -> QR) to the door camera,
     OR tap your registered RFID card/tag on the reader.
  2. Step 2 - within about 20 seconds, place your finger on the fingerprint
     reader OR look at the camera for Face ID.
  The door opens only if step 2 belongs to the same person as step 1. The QR
  works only {window}, only for the lab it was booked for, and stops working if
  the booking is cancelled. Tips: raise screen brightness, hold the phone
  steady 15-25 cm from the camera, do not use a screenshot of an old booking.

Registering fingerprint and Face ID: every new account gets a door identity
(USERn). Visit lab staff or an administrator: they store your finger on the
door's fingerprint reader and take about 20 photos of your face for Face ID.
Until then step 1 can pass but step 2 cannot. The Profile page shows what is
still pending. RFID cards are issued by staff too; the QR code works without one.

Why a door refuses you (reason codes as staff and the Access page show them):
{reasons}
  - WRONG FINGER / FACE MISMATCH: step 2 matched someone else's biometric.

Problems: use "Report an issue" (top bar) with the lab, a description and
photos; staff are notified and you can follow the ticket under "My reports".
The bell icon shows notifications (booking confirmations, reminders,
maintenance updates, account setup).

Behind the scenes: the portal (web app, server and database) runs on the lab
computer. The door controller (an ESP32 with the RFID reader, fingerprint
reader, lock relay and screen) asks the portal whether a QR booking is valid,
then checks the biometric itself; a second ESP32 camera reads QR codes and
sends faces to the face-recognition service. An automation service (n8n)
sends reminders, briefings and daily/weekly reports and flags unusual events;
it cannot open doors. The AI assistant is read-only and cannot book, cancel or
open anything. If the portal is down, booking QR codes are refused (the door
fails safe); tell lab staff."""
