"""
Seed the database with the real laboratory, the two enrolled users, and the
devices that already exist on the bench.

The auth_subject values (USER1 / USER2) and the RFID UIDs are taken from the
working firmware - they are the join between this database and the embedded
system, so they must match exactly.

Run:  python seed.py
"""
from datetime import datetime, timezone

from sqlalchemy import select

from app.core.security import hash_password
from app.db.session import Base, SessionLocal, engine
from app.models import (Asset, AssetStatus, Device, DeviceType, Lab,
                        RfidCredential, Role, RoleRow, User)

Base.metadata.create_all(engine)
db = SessionLocal()


def get_or_create(model, defaults=None, **kw):
    obj = db.scalar(select(model).filter_by(**kw))
    if obj:
        return obj, False
    obj = model(**{**kw, **(defaults or {})})
    db.add(obj)
    db.flush()
    return obj, True


# --- roles ------------------------------------------------------------------
for r, desc in [("STUDENT", "Books laboratories and opens doors they booked"),
                ("LAB_STAFF", "Manages bookings, assets and alerts"),
                ("ADMIN", "Full administrative control")]:
    get_or_create(RoleRow, {"description": desc}, name=r)

# --- users ------------------------------------------------------------------
# auth_subject MUST match the face-server labels and the firmware's
# authorizedUsers[].name, or step 2 can never be bound to step 1.
admin, _ = get_or_create(
    User, {
        "full_name": "System Administrator",
        "hashed_password": hash_password("Admin#2026"),
        "role": Role.ADMIN,
        "department": "Robotics & Automation",
    }, email="admin@giu-uni.de")

ali, _ = get_or_create(
    User, {
        "full_name": "Ali Loay",
        "hashed_password": hash_password("Student#2026"),
        "role": Role.STUDENT,
        "auth_subject": "USER1",
        "student_id": "GIU-RAE-2023",
        "department": "Robotics & Automation Engineering",
    }, email="ali@giu-uni.de")

ramy, _ = get_or_create(
    User, {
        "full_name": "Dr. Ramy Amir Shawkey Shenouda",
        "hashed_password": hash_password("Staff#2026"),
        "role": Role.LAB_STAFF,
        "auth_subject": "USER2",
        "department": "Robotics & Automation Engineering",
    }, email="ramy@giu-uni.de")

# --- labs -------------------------------------------------------------------
# The real GIU laboratories.
#
# LABS are the bookable entity, not majors. A booking reserves a physical room
# with a door, and a QR token is bound to one lab_id - so a discipline cannot
# be the unit of reservation. `category` exists purely so students can browse
# by field.
#
# has_controller marks the laboratories that actually have door hardware.
# Exactly one does today. The portal shows "No door hardware" for the rest
# rather than implying a lock that is not there.
LAB_SPECS = [
    # code,     name,                                   category,                 location,               cap, hw
    ("LAB_01", "Robotics & Industrial Automation Laboratory", "Robotics & Automation",
     "UR5e and FANUC industrial arms, conveyor systems and automation cells with "
     "workstation PCs.", "Building C, Level 2", 16, True),

    ("LAB_02", "PLC & Control Systems Laboratory", "Robotics & Automation",
     "Siemens S7-1200 trainer benches for programmable logic control and SCADA.",
     "Building C, Level 1", 20, False),

    ("LAB_03", "Production Engineering Laboratory", "Manufacturing",
     "Drilling, bending and forming machines for conventional manufacturing "
     "processes.", "Building B, Ground Floor", 18, False),

    ("LAB_04", "Materials Testing Laboratory", "Materials",
     "Tensile testing machines, materials characterisation equipment and 3D "
     "printers.", "Building B, Level 1", 14, False),

    ("LAB_05", "Automotive Engineering Laboratory", "Automotive",
     "Two sectioned electric vehicles for powertrain and systems teaching.",
     "Building A, Ground Floor", 12, False),

    ("LAB_06", "Electronics & PCB Laboratory", "Electrical",
     "Soldering stations, PCB assembly and electronics prototyping benches.",
     "Building D, Level 1", 20, False),

    ("LAB_07", "Microcontrollers Laboratory", "Electrical",
     "Microcontroller development kits with Proteus simulation workstations.",
     "Building D, Level 2", 24, False),

    ("LAB_08", "Electrical Power Laboratory", "Power",
     "Electrical machines, motors and power systems test benches.",
     "Building D, Ground Floor", 16, False),

    ("LAB_09", "Design & Fabrication Laboratory", "Design",
     "Jewellery furnace, woodworking, laser and heat cutting equipment.",
     "Building E, Ground Floor", 12, False),

    ("LAB_10", "CAD & Digital Design Laboratory", "Design",
     "Workstations for AutoCAD, Fusion 360 and 3D modelling.",
     "Building E, Level 1", 26, False),

    ("LAB_11", "Fashion & Textiles Laboratory", "Fashion",
     "Sewing and garment construction equipment.",
     "Building E, Level 2", 18, False),
]

labs = {}
for code, name, category, desc, location, cap, hw in LAB_SPECS:
    lab, _ = get_or_create(Lab, {
        "name": name,
        "category": category,
        "description": desc,
        "location": location,
        "capacity": cap,
        "has_controller": hw,
        "exclusive_booking": True,
        # False preserves the existing local RFID + biometric behaviour
        # exactly. Set True to require an active booking for RFID entry.
        "require_booking_for_rfid": False,
    }, code=code)
    labs[code] = lab

robotics = labs["LAB_01"]

# --- RFID credentials (from the working firmware) ---------------------------
get_or_create(RfidCredential, {"label": "Blue tag", "user_id": ali.id},
              uid_hex="8952FF1F")
get_or_create(RfidCredential, {"label": "White card", "user_id": ramy.id},
              uid_hex="F577308E")

# --- devices on the bench ---------------------------------------------------
get_or_create(Device, {
    "name": "Door Controller (Master ESP32)",
    "device_type": DeviceType.MASTER_CONTROLLER,
    "lab_id": robotics.id,
}, device_uid="MASTER_LAB01")

get_or_create(Device, {
    "name": "Entry Camera (ESP32-CAM)",
    "device_type": DeviceType.CAMERA,
    "lab_id": robotics.id,
    "ip_address": "192.168.1.150",
}, device_uid="CAM_LAB01")

get_or_create(Device, {
    "name": "Face Recognition Server",
    "device_type": DeviceType.FACE_SERVER,
    "lab_id": robotics.id,
    "ip_address": "192.168.1.8",
}, device_uid="FACESRV_01")

# --- equipment ---------------------------------------------------------------
ASSETS = [
    ("RB-001", "UR5e Collaborative Arm",        "Manipulator",  "LAB_01"),
    ("RB-002", "FANUC LR Mate 200iD",           "Manipulator",  "LAB_01"),
    ("RB-003", "Belt Conveyor Module",          "Automation",   "LAB_01"),
    ("PLC-001", "Siemens S7-1200 Trainer",      "PLC",          "LAB_02"),
    ("PLC-002", "HMI Panel KTP700",             "PLC",          "LAB_02"),
    ("PR-001", "Pillar Drilling Machine",       "Machine tool", "LAB_03"),
    ("PR-002", "Sheet Metal Bending Brake",     "Machine tool", "LAB_03"),
    ("MT-001", "Universal Tensile Tester",      "Instrument",   "LAB_04"),
    ("MT-002", "Prusa MK4 3D Printer",          "Fabrication",  "LAB_04"),
    ("AU-001", "Sectioned EV Powertrain Rig",   "Vehicle",      "LAB_05"),
    ("EL-014", "Rigol DS1054Z Oscilloscope",    "Instrument",   "LAB_06"),
    ("EL-021", "Hot Air Rework Station",        "Tool",         "LAB_06"),
    ("MC-001", "STM32 Nucleo Development Kit",  "Dev board",    "LAB_07"),
    ("PW-001", "Three-Phase Induction Motor Rig", "Machine",    "LAB_08"),
    ("DS-001", "CO2 Laser Cutter",              "Fabrication",  "LAB_10"),
    ("TX-001", "Industrial Overlock Machine",   "Textile",      "LAB_11"),
]
for tag, name, cat, lab_code in ASSETS:
    target = labs.get(lab_code)
    if target is None:
        continue
    get_or_create(Asset, {"name": name, "category": cat,
                          "lab_id": target.id,
                          "status": AssetStatus.AVAILABLE}, asset_tag=tag)

db.commit()

print("Seed complete.")
print()
print("  Sign in with:")
print("    admin@giu-uni.de / Admin#2026      (ADMIN)")
print("    ali@giu-uni.de   / Student#2026    (STUDENT, auth_subject USER1)")
print("    ramy@giu-uni.de  / Staff#2026      (LAB_STAFF, auth_subject USER2)")
print()
print(f"  Labs: {len(LAB_SPECS)} seeded. LAB_01 is the only one with door hardware.")
print("  Change these passwords before any real deployment.")
db.close()
