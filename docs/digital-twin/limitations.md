# Digital twin: limitations

- **Read-only by design.** No motion control exists; control adapters stay UNAVAILABLE until the owner signs off a commissioning step (docs/ROBOT_CONTROL.md).
- **Not hard real-time.** The latest state is reported every 0.2 s and polled by the portal; brief fast motions can be smoothed.
- **FANUC not verified on hardware.** The controller's IP and page format are still to be inspected; until then the FANUC twin shows TELEMETRY UNAVAILABLE rather than a guessed pose.
- **Mesh proportions.** The FANUC ER-4iA uses LR Mate 200iD meshes; joint angles map correctly, link lengths may differ.
- **Telemetry outage.** After 2 s without data the twin shows TELEMETRY STALE; the camera can still report visual motion.
