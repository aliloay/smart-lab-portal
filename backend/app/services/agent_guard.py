"""Portal assistant guard (Gemini independent audit, 23 Nov 2026 - K5, K10).

The knowledge assistant (tools/knowledge/agent.py) refuses control and secret requests before any model runs; the
portal assistant relied on its system prompt alone. This runs first for every portal question (staff and student):

  * control requests ("open the door", "move the UR5e", "I want you to unlock the lab") get a fixed answer - the
    assistant controls nothing; the door opens only from the Master ESP32, robots stay read-only;
  * requests for secrets (passwords, keys, tokens, .env) get a fixed refusal;
  * the Robotics Lab opening hours (owner, 23 Nov) are answered exactly - students never reached the knowledge FAQ.

Questions about HOW something works ("how does the door open?") are not requests and pass through.
"""
from __future__ import annotations

import re
from typing import Optional

_ACT_VERB = (r"(move|jog|drive|home|start|stop|reset|run|open|unlock|lock|close|trigger|activate|deactivate|disable|"
             r"enable|arm|disarm|power (?:on|off)|turn (?:on|off)|restart|reboot|shut ?down|flash|actuate|release)")
_ACT_TARGET = (r"(robots?|ur5e|ur ?5|fanuc|arm|gripper|doors?|lock|relay|alarm|siren|buzzer|emergency|esp32|"
               r"solenoid|lab door|the lab)")
_QUESTION_START = re.compile(r"(?i)^\s*(how|why|what|when|where|who|which|does|do|is|are|was|were|explain|describe)\b")
ACTION = re.compile(
    rf"(?i)^\s*(please\s+|pls\s+|can you\s+|could you\s+|would you\s+|will you\s+|go (and )?|now\s+)?{_ACT_VERB}\b.*\b{_ACT_TARGET}\b"
    rf"|\b(i want you to|i need you to|i'd like you to|you should|use the \w+ to|make the \w+|tell the \w+ to)\b.*\b{_ACT_VERB}\b.*\b{_ACT_TARGET}\b")
SECRET = re.compile(
    r"(?i)\b(what(?:'s| is| are)|show|print|give|tell me|reveal|dump|send|display|read out|contents? of|value of|leak)\b.*"
    r"\b(passwords?|passwd|api[ _-]?keys?|device[ _-]?keys?|secrets?|tokens?|credentials?|private keys?|jwt|"
    r"service[_ ]key|x-kb-key|rtsp)\b|\.env\b|camera2?\.env|robot\.env")
HOURS = re.compile(
    r"(?i)\b(open(ing)?|close|closing|hours?|timings?|schedule|what time|until when)\b.*\b(lab|labs|robotics)\b"
    r"|\b(lab|labs|robotics)\b.*\b(open(ing)?|close|closing|hours?|timings?|what time)\b")
_HOURS_NOT = re.compile(r"(?i)\b(door|booking|book|lock|unlock|n8n|workflow|report|backup|now|currently|today|free|"
                        r"empty|available|occupied|busy|which labs|are any)\b")
_EXPLAIN = re.compile(r"(?i)^\s*(what (is|are) (an?|device|api)\b|how\b|why\b|explain\b|describe\b)")

ACTION_TEXT = ("I can't control anything. Only the Master ESP32 at the door opens the lab door, after your card or "
               "QR and your fingerprint or face. The robots are monitored read-only and are moved only by trained "
               "staff at their own pendants. For help, ask the lab staff.")
SECRET_TEXT = ("I can't share passwords, keys, tokens or configuration secrets. Ask the lab administrator if you "
               "need access.")
HOURS_TEXT = ("The Robotics Lab follows the university's five teaching slots: it opens at **8:30 AM** (slot 1) and "
              "closes at **5:15 PM** (end of slot 5, 3:45-5:15 PM). Book a slot on the Bookings page.")


def check(question: str) -> Optional[tuple[str, str]]:
    """(intent, fixed answer) or None."""
    q = (question or "").strip()
    if not q:
        return None
    if SECRET.search(q) and not _EXPLAIN.match(q):
        return "guard_secret", SECRET_TEXT
    if ACTION.search(q) and not _QUESTION_START.match(q):
        return "guard_action", ACTION_TEXT
    if HOURS.search(q) and not _HOURS_NOT.search(q):
        return "opening_hours", HOURS_TEXT
    return None
