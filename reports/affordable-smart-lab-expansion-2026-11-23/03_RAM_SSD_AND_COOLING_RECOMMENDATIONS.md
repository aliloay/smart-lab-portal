# RAM, SSD and cooling
| Question | Answer |
|---|---|
| More RAM? | **No.** 32 GB is the firmware maximum and both slots are used. 64 GB was excluded and does not fit this firmware limit. |
| Faster RAM? | No. The processor platform runs the 3200 modules at 2667. |
| SSD? | **Not now.** C: is a healthy NVMe with about 80 GB free and Docker already sits on it. |
| When would an SSD help? | If C: stays under about 40 GB free, or the hard disk D: reports errors. Then a 1 TB 2.5" SATA SSD in place of D: (Crucial BX500 from 5,999 EGP, snapshot). It would be a **data** disk; no system clone is needed and none was made. Back up D: first. |
| Cooling | 53 C idle and no throttling events: no measured problem. Dust cleaning by a technician is reasonable maintenance; thermal paste only after a load test shows throttling. No cooler price was verified. |

## Free actions, best first
1. Before a demo close Chrome tabs and VS Code (about 10 GB at the measurement).
2. Keep Docker on C:. Keep videos, training data and backups on D:.
3. Use the mains adapter and the "Best performance" slider during the defense; the plan was Balanced (owner decision, not changed).
4. Read SMART wear once as administrator (command below) and keep the number.
5. Keep `.wslconfig` at 10 GB; there is no measurement that asks for more.

```powershell
Get-PhysicalDisk | Get-StorageReliabilityCounter | Select-Object DeviceId, Wear, ReadErrorsTotal, PowerOnHours
```

**Best affordable laptop upgrade: none (0 EGP); tidy memory use and keep Docker on C:.**
