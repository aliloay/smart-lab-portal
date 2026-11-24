# FAQ: labs, door access and accounts

## Q: Where is the Robotics Lab?
Also asked: where is LAB_01, robotics lab location, which room is the robotics lab
**A:** The Robotics Lab (LAB_01) is recorded as Building S, Floor 2, Room 224. Admins can change the location on the lab's page.
Source: `labs.location` (live value; edited from the Laboratories page), 21 Nov 2026

## Q: When is the Robotics Lab open?
Also asked: robotics lab opening hours, what time does the robotics lab open, when does the robotics lab close, when does the lab close, when does the robotics lab open, lab working hours, lab timings, lab schedule
**A:** The Robotics Lab follows the university's five teaching slots. It opens at 8:30 AM, when slot 1 starts, and closes at 5:15 PM, when slot 5 ends (slot 5 runs 3:45 to 5:15 PM). That is 8 hours 45 minutes a day. Each slot is about 1.5 hours.
Source: owner (lab hours follow the GIU slot timetable), 23 Nov 2026

## Q: How many labs are there?
Also asked: number of labs, list of labs, which labs exist
**A:** Live: the portal assistant lists the labs from the records ("How many labs are there?"). Historical count (21 Nov 2026, not live): 11 registered, 10 active.
Source: `labs` table (live), checked 21 Nov 2026

## Q: How can I open the lab door?
Also asked: door access methods, how do I get in, how does door access work
**A:** Two steps at the door. First identify yourself with your RFID card or a QR code (a booking QR or your personal door QR). Then confirm with your own fingerprint or face. The second step must match the first.
Source: `firmware/SmartLab_Master_Portal/SmartLab_Master_Portal.ino` (STEP 1 / STEP 2), `docs/ACCESS_FLOW.md`

## Q: Which device opens the door?
Also asked: what controls the lock, who unlocks the door, can the portal open the door
**A:** Only the Master ESP32 (MASTER_LAB01) drives the lock relay. The portal and the backend never open the door; they only answer whether an identity is valid.
Source: `backend/app/services/access.py` (module docstring), `CLAUDE.md`

## Q: What is a personal door QR?
Also asked: door QR anytime, QR without booking, master QR
**A:** A QR code that belongs to one person and works anytime, under the same rule as an RFID card. Create it on your Profile page under Door QR. You still need your fingerprint or face after showing it.
Source: `backend/app/services/access.py` (`validate_personal_qr`), `frontend/src/components/DoorQrCard.tsx`

## Q: Can I use my booking QR outside my booking time?
Also asked: QR expired, booking QR not working, QR before booking
**A:** No. A booking QR is valid only between the booking's start and end (grace BOOKING_GRACE_MINUTES, 0 by default). Outside that window the door refuses it.
Source: `backend/app/services/access.py` (`validate_qr`), `backend/app/core/config.py`

## Q: Does the door work without the laptop?
Also asked: offline door, laptop down door, network down access, what happens to the door when the laptop is off
**A:** Partly. RFID card plus fingerprint keep working, because both are checked inside the master. QR and face need the laptop and are refused while it is unreachable. Door events are stored on the master and sent later with their real time.
Source: `docs/reports/MEASUREMENTS_2026-11-21.md` (test D), `firmware/SmartLab_Master_Portal` (store and forward, portal-1.2)

## Q: How fast does the door open?
Also asked: door speed, unlock time, how long does access take
**A:** Measured on 21 Nov: after the fingerprint or face matches, the lock releases in 5–8 ms. A QR adds about 160 ms for the booking check. The grant screen appears 230 ms after unlocking.
Source: `docs/reports/MEASUREMENTS_2026-11-21.md` (test A)

## Q: How long does a sign-in last?
Also asked: session length, when am I logged out, token expiry
**A:** 8 hours (ACCESS_TOKEN_EXPIRE_MINUTES = 480), then you sign in again.
Source: `backend/app/core/config.py`

## Q: Why can't I sign in after signing up?
Also asked: account pending, account disabled after sign up, waiting for approval
**A:** New accounts need an administrator's approval first. Until an admin approves the account on Users & roles, it cannot sign in.
Source: `backend/app/api/routes/auth.py` (signup), `backend/app/core/config.py` (SIGNUP_REQUIRES_APPROVAL)

## Q: Who approves new accounts?
Also asked: who can activate an account, approval of sign ups
**A:** Administrators, on the Users & roles page. Lab staff cannot activate accounts.
Source: `backend/app/api/routes/admin.py` (`update_user`, staff-editable fields)

## Q: What photo appears on the door screen when I enter?
Also asked: grant screen photo, door photo, tablet photo
**A:** The photo an admin chose for you (Users → Enroll → Door photo): a face-training frame, a door-camera picture or an upload. Without a chosen photo, the best face-enrollment frame is used.
Source: `firmware/face_server/face_server.py` (portrait routes), `frontend/src/components/DoorPhoto.tsx`
