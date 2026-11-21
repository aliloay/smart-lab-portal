# Smart Lab FAQ: short answers

Curated question → answer pairs for the most common laboratory questions (2026-11-21). The knowledge assistant answers
a question that clearly matches one of these **instantly, without the AI model**, and cites the file. Anything that
does not match goes through the normal search + answer path.

## How the files are written
- Each question is a heading `## Q: …`, followed by an `Also asked:` line, a one-line `**A:**` answer and a
  `Source:` line naming the file, table or endpoint that proves it.
- **Static facts only.** Values that change are marked **Live**. The answer says where the live value comes from; the
  portal assistant reads it from the records at question time (device status, counts, IPs, stock, bookings).
- When a source changes, update the answer here in the same commit.

## Files
| File | Topics |
|---|---|
| [lab-and-access.md](lab-and-access.md) | labs, door access methods, QR, sign-in, accounts |
| [devices-and-esp32.md](devices-and-esp32.md) | the five ESP32 boards, what each one does, bins, environment |
| [robots-and-pcs.md](robots-and-pcs.md) | UR5e, FANUC, digital twins, lab PCs, Hemaly's PC |
| [cameras-ar-ai.md](cameras-ar-ai.md) | security cameras, AR scan, AI models, knowledge base |
| [automation-reports-backups.md](automation-reports-backups.md) | n8n workflows, daily / weekly / monthly reports, backups |
| [troubleshooting.md](troubleshooting.md) | common problems and what they mean |
