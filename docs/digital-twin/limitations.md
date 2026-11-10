# Digital twin: limitations

- **Read-only by design.** No motion control exists; control adapters stay UNAVAILABLE until the owner signs off a commissioning step (docs/ROBOT_CONTROL.md).
- **Not hard real-time.** The latest state is reported every 0.2 s and polled by the portal; brief fast motions can be smoothed.
- **FANUC verified in one session.** The read-only twin followed the pendant on 14 Oct 2026 at about 3 samples/s. Still open: confirming the J2/J3 coupling against known poses, the mesh proportions (LR Mate 200iD meshes stand in for the ER-4iA), and the controller battery warning (DIAG-009). If the page cannot be read, the twin shows TELEMETRY UNAVAILABLE, never a guessed pose.
- **Mesh proportions.** The FANUC ER-4iA uses LR Mate 200iD meshes; joint angles map correctly, link lengths may differ.
- **Telemetry outage.** After 2 s without data the twin shows TELEMETRY STALE; the camera can still report visual motion.
