# Contributing

1. Branch from `main` (it is protected: changes go in through pull requests).
2. Keep changes to existing behaviour; physical behaviour (door timing, access sequence, emergency controls) and robot control need the owner's approval.
3. Run the checks before opening a pull request:

```powershell
docker compose run --rm --no-deps -T -v "${PWD}\backend:/app" backend python -m pytest -q -p no:cacheprovider   # backend, on smartlab_test
py -m pytest -q tools/security_vision
py -m pytest -q tools/robot_monitor tools/knowledge tools/pc_agent tools/relay
cd frontend; npx tsc --noEmit; npx vite build
```

4. Never commit secrets, `.env`, `secrets.h`, camera files, photos of people, datasets or database dumps.
5. Describe what was tested and what could not be (hardware, offline).
