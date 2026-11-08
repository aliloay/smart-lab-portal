# Enclosure reference photos (owner)

Put JPEG photos of each printed enclosure in the folder named after its marker code (':' -> '_'):

    SLAB_D_BIN_NODE_1/   SLAB_D_REUSE_BIN_1/   SLAB_D_MASTER_LAB01/   SLAB_D_ENV_LAB01/

Per enclosure, 10 photos (phone camera, max ~1600 px, the box filling most of the picture):
1-4. front, back, left side, right side (straight on)
5-6. 45 deg front-left and 45 deg front-right
7.   top (looking down)
8.   in place on its bench under normal lab lighting
9.   from 1-2 m away (the box small in the picture)
10.  with another enclosure or a PC partly in the picture (a distractor)

No people in the photos. Then: `docker compose exec backend python -c "from app.services import appearance as a;
print(a.evaluate(a.Matcher().load()))"` - leave-one-out; `wrong` must be 0 before the hint is shown in the camera.
The photos are not committed (git-ignored); only this README and manifest.json are.
