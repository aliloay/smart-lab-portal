# FAQ: facts the 24 Nov 2026 benchmark showed the model gets wrong

## Q: What is the FANUC controller model?
Also asked: fanuc controller type
**A:** R-30iB Mate Plus (label 2021-03). The robot is a FANUC ER-4iA; the portal's 3D arm is an LR Mate 200iD stand-in.
Source: `docs/FANUC_LIVE_TWIN.md`

## Q: What database does the portal use?
Also asked: portal database, which database does the portal use
**A:** PostgreSQL 16, in a Docker container on the laptop.
Source: `docker-compose.yml`

## Q: How are embeddings generated?
Also asked: how does the knowledge search create embeddings
**A:** Locally by Ollama with the model nomic-embed-text, on the CPU, one vector per document chunk. A question is embedded the same way, and the cosine score is blended with BM25 keyword search.
Source: `tools/knowledge/kb.py`

## Q: What is the CO2 level in the lab?
Also asked: co2 level, what is the co2 concentration
**A:** It is not measured. The environment node reports temperature, humidity, gas/smoke, flame and motion; there is no CO2 reading.
Source: `backend/app/services/environment.py`

## Q: What does the radiation sensor measure?
Also asked: radiation level
**A:** The lab has no radiation sensor in this project. The environment node reports temperature, humidity, gas/smoke, flame and motion.
Source: `backend/app/services/environment.py`
