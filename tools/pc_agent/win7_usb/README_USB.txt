SMART LAB - PC AGENT, OFFLINE PACKAGE FOR WINDOWS 7 (2026-10-21)

1. Copy this whole folder (win7_usb) to a USB stick, then to the PC (e.g. Desktop).
2. Right-click install.bat -> Run as administrator. Wait for "Done" (2-5 minutes).
   - If Python says "api-ms-win-crt ... missing": restart Windows and run install.bat again.
3. A minimised window "Smart Lab - PC agent" appears. Leave it running.
   From now on it starts by itself every time someone signs in to Windows.
4. In the portal (Lab Equipment -> Robots & PCs) PC-01 shows "running" with the
   signed-in user, its IP and "agent 0.8". View screen / Message / Lock now work.

The PC is shown ON / OFF in the portal even WITHOUT this agent (the lab laptop
checks it on the LAN by its MAC address). The agent adds the details and controls.

agent\agent.env holds THIS PC's own key (PC-01). Do not copy it to another PC:
another PC needs its own key (portal: Devices -> the PC -> Issue own key).
Undo: uninstall.bat (as administrator).
