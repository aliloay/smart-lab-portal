# Smart Lab PC kit

PowerShell only, no administrator rights. Full guide: `SMART_LAB_POWERSHELL_PC_DEPLOYMENT_GUIDE.md`.

**Each Windows account that should have the agent runs this once, under its own login:**

1. Open this folder.
2. Right-click `Install-CurrentUser.ps1` -> **Run with PowerShell**.
3. Wait for the green `OK` lines, press Enter.

A yellow `WAIT` line is not an error: the agent registers by itself when the portal can be reached.

| File | Use |
|---|---|
| `Install-CurrentUser.ps1` | Install, repair or upgrade for this account |
| `Check-CurrentUser.ps1` | Health check. Only reads, never prints a key |
| `Start-Agent.ps1` / `Stop-Agent.ps1` | Start now, or stop until the next sign-in |
| `Uninstall-CurrentUser.ps1` | Remove it for this account |
| `site.json` | Network addresses of this site. Change them here, not in the scripts |

If Windows says running scripts is disabled and the right-click option is missing or refused, stop and ask GIU IT. Do not work around it.
