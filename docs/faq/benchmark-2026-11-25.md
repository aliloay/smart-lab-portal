# FAQ: facts the 25 Nov 2026 benchmark showed the model gets wrong

## Q: How does the door decide who may enter?
Also asked: who decides if the door opens, how does the door check a person
**A:** The Master ESP32 decides. Step 1 is a card or a QR code (the backend checks a QR and returns one identity), step 2 is a fingerprint or the face at the entrance. Both must be the same person. Cameras inside the lab, the portal and the assistants never open it, and a failed check leaves it locked.
Source: `docs/ARCHITECTURE.md`

## Q: How is a person named by the cameras?
Also asked: how do the cameras know who someone is, how does a camera confirm a name
**A:** A confirmed name comes from a door entry, this camera's own face match, or staff confirmation. The other camera's confirmed name is taken over when the floor positions match, or by elimination (the one unnamed person and the one free name). Clothes, a desk or a seat only give a marked guess with a question mark.
Source: `tools/security_vision/crosscam.py`

## Q: How many n8n workflows are there?
Also asked: number of n8n workflows, how many workflows does the lab have
**A:** 27 in the knowledge index of 25 Nov 2026: 26 plus the central error handler. They read, alert and report; none opens the door or moves a robot. The Automations tab shows the current number.
Source: `automation/n8n/json`
