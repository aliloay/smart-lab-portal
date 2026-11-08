#!/usr/bin/env bash
# Polls the owner's public Drive folder until the training zip is there, then downloads it (2026-10-28).
cd "$(dirname "$0")"
URL="https://drive.google.com/drive/folders/12DlDTUkGZK3G37YGxNNONLzUJKG07xrk"
for i in $(seq 1 72); do
  .venv/Scripts/python.exe -m gdown --folder "$URL" -O data/raw_owner >> data/fetch.log 2>&1
  if ls data/raw_owner/*/*.zip data/raw_owner/*.zip 2>/dev/null | grep -q zip; then
    z=$(ls data/raw_owner/*.zip data/raw_owner/*/*.zip 2>/dev/null | head -1)
    # a finished download is not smaller than ~10 MB and passes the zip test
    if [ "$(stat -c %s "$z")" -gt 10000000 ] && .venv/Scripts/python.exe -c "import zipfile,sys;zipfile.ZipFile(sys.argv[1]).testzip()" "$z" 2>/dev/null; then
      echo "DOWNLOADED $z $(stat -c %s "$z") bytes"; exit 0
    fi
  fi
  echo "waiting ($i) $(date +%H:%M)"; sleep 300
done
echo "GAVE UP after 6 h"
