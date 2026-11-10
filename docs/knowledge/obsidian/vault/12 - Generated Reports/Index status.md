---
type: "report"
generated: true
updated: "2026-11-04T00:02:43+02:00"
---

# Index status

- Sources present: 296
- Chunks indexed: 11111 (built 2026-11-04T00:02:43+02:00)
- Last scan: new 0, changed 9, unchanged 287, removed 0, renamed 0, errors 0

## Redacted before indexing (kinds only, never values)
- `README.md`: secret-assignment
- `backend/app/api/routes/admin.py`: secret-assignment
- `backend/app/api/routes/auth.py`: secret-assignment
- `backend/app/api/routes/bookings.py`: secret-assignment
- `backend/app/api/routes/security.py`: secret-assignment
- `backend/app/models/tables.py`: secret-assignment
- `backend/app/services/access.py`: secret-assignment
- `backend/app/services/ai.py`: secret-assignment
- `backend/app/services/booking.py`: secret-assignment
- `backend/app/services/briefing.py`: configured-literal
- `backend/app/services/drift.py`: secret-assignment
- `backend/app/services/emergency.py`: secret-assignment
- `backend/app/services/qr.py`: secret-assignment
- `backend/app/services/storage.py`: secret-assignment
- `docker-compose.yml`: secret-assignment
- `docs/ARCHITECTURE.md`: secret-assignment
- `docs/camera-identity/TWO_CAMERAS.md`: rtsp-credentials
- `tools/security_vision/security_vision.py`: rtsp-credentials
- `tools/security_vision/test_camera_reconnect.py`: rtsp-credentials
- `tools/security_vision/test_masking.py`: rtsp-credentials
- `tools/security_vision/test_two_cameras.py`: rtsp-credentials

## Removed from the repository (flagged, notes kept)

## Never read (deny list)
```
*.env
.env*
*/.env*
*secrets.h
*camera.env
*robot.env
*.pem
*.key
*.crt
*.dump
*.sql
*.sqlite*
*.jpg
*.jpeg
*.png
*.mp4
*.onnx
*.bin
*.zip
*/node_modules/*
*/.git/*
*/__pycache__/*
*/build/*
*/dist/*
*/.venv/*
docs/paper_images_private/*
*/dataset*/*
*/recordings/*
*/backups/*
deploy/tls/*
*/e2e/*
*/fanuc_probe_out/*
*user_photos*
```
