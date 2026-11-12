# Backup service image (2026-11-12): postgres:16-alpine + openssl, so dumps can be encrypted (AES-256) when
# BACKUP_PASSPHRASE is set. Built once with internet; runs offline at the lab afterwards.
FROM postgres:16-alpine
RUN apk add --no-cache openssl
