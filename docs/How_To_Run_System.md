Terminal 1:"Backend"   [ http://localhost:8000/api/docs#/ ]

cd "C:\Users\dell\OneDrive\Desktop\Bsc\codes\smart-lab-portal\backend"
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.venv\Scripts\activate
alembic upgrade head
python seed.py
uvicorn app.main:app --host 0.0.0.0 --port 8000

------------------------------------------------------------------------------------------------------------------------
Terminal 2:"Main Server (laptop)"

cd "C:\Users\dell\OneDrive\Desktop\Bsc\codes\draft_codes\face_server"
python face_server.py

------------------------------------------------------------------------------------------------------------------------
Terminal 3:"Frontend"  [ http://localhost:5173 ]

cd "C:\Users\dell\OneDrive\Desktop\Bsc\codes\smart-lab-portal\frontend"
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
npm install
npm run dev

------------------------------------------------------------------------------------------------------------------------
PGadmin for observing tables of db in windows
------------------------------------------------------------------------------------------------------------------------
LogIn Credentials:

ali@giu-uni.de	        (password: see README - not stored here)	     Student — you, USER1
admin@giu-uni.de     	(password: see README - not stored here)	         Administrator
ramy@giu-uni.de	        (password: see README - not stored here)	         Lab staff — Dr. Ramy, USER2
hemaly@giu-uni.de	(password: see README - not stored here)	         Lab staff — Eng. Hemaly (lab engineer, master PC), USER5