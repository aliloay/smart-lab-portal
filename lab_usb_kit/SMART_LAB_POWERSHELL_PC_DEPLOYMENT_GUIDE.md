# Smart Lab PC agent: PowerShell deployment guide

Kit version 1.1, 7 November 2026. For lab engineers and the Smart Lab administrator.

## Test status: read this first

| Tested | Result |
|---|---|
| Agent, DPAPI code from PowerShell, enrolment, supervisor, duplicates, crash recovery, portal loss and return, restart | Passed on the portal laptop as a standard user, against a stub portal (14 checks) |
| Agent unit tests | 40 passed |
| Per-account keys on the backend | Passed in tests. **Live only once the backend with this change is deployed** (see Upgrade) |
| The five `.ps1` scripts | **Syntax checked only. They have not been executed.** Script execution is disabled on the test laptop, and that setting was not overridden |
| A second Windows account | **Not tested.** Only one account was available |
| A real GIU lab PC, the relay and screen sharing with this kit | **Not tested** |

So the first install at the lab is itself a test. Do one PC, run the check, and only then continue.

## Why the agent starts the way it does

| Your requirement | What the kit does |
|---|---|
| Current-user start-up | One value under `HKCU\...\Run`. No service, no HKLM, no SYSTEM task. The old 5-minute scheduled task is removed |
| No console window | `pythonw.exe` starts hidden |
| Visible indicator | A Smart Lab icon in the notification area: running, waiting for the portal, or screen being viewed |
| No duplicates | One supervisor per session (mutex), one agent per PC (exclusive local port) |
| Several accounts | Each runs the installer. Only one agent can speak for a PC at a time; a second signed-in account waits and takes over when the first signs out |
| Credentials | Each account gets its own PC key from the portal, stored with DPAPI so that only that account on that PC can read it. The Master ESP32 key is not on the stick, and the kit build refuses to finish if it finds it |
| Screen capture | Only while staff have the view open. A notice appears and the icon changes |

## Limits you should know about

1. **Install folder.** You asked for the application-data folder, but on 4 November the university's security software removed programs from `AppData` within minutes. The kit uses `%USERPROFILE%\SmartLab`. If security removes it there as well, the installer stops and says so. It does not move the files to try again. **That is a policy decision for GIU IT.**
2. **Execution policy.** The kit does not use `-ExecutionPolicy Bypass` or `iex`. The older README suggested `iex (gc -Raw ...)`, which sidesteps the policy, so it has been removed. Windows' own right-click **Run with PowerShell** was what worked at the lab on 4 November. If it stops working, ask IT.
3. **Relay.** The relay on the engineer's PC forwards only the portal's ports, and only from the listed subnets. It still connects the GIU network to the Smart Lab network, so **get written approval from GIU IT or Dr. Ramy for it.** I have no record of that approval. On 4 November the relay worked only with `python.exe`, because that was the program the firewall allowed. Please check that this firewall rule is itself approved.
4. **Enrolment code.** Anyone holding the stick's `enroll.key` can register a key for a PC while enrolment is open. Set `PC_ENROLL_OPEN=false` on the portal when you are not installing, and keep the stick safe. Every enrolment is in the audit log.
5. **Other accounts.** One user's install never configures another account.

## Install

For each authorized Windows account on each PC, signed in as that account:

1. Open the `lab_usb_kit` folder on the stick.
2. Right-click `Install-CurrentUser.ps1` -> **Run with PowerShell**.

Do the engineer's PC first. It is recognized from `site.json`, or you can force it from a PowerShell window in the kit folder:

    .\Install-CurrentUser.ps1 -Role Engineer

Expected output:

    Smart Lab 1.1 on <PC> for account <you> as PC_<PC>
    OK    agent running. Look for the Smart Lab icon in the notification area.
    OK    this account has its own key for PC_<PC>, protected with DPAPI

`WAIT` means the portal cannot be reached yet. The agent keeps trying by itself.

## Daily commands

    .\Check-CurrentUser.ps1          # health; -Full also checks the stick's files
    .\Start-Agent.ps1                # start now
    .\Stop-Agent.ps1                 # stop until the next sign-in
    .\Uninstall-CurrentUser.ps1      # remove for this account

## Upgrade

1. **Deploy the backend first:** `py -I tools/deploy/deploy.py --allow-migration` on the laptop. It adds one table, and nothing existing changes. An older backend ignores the account field and replaces the PC's single key, which is fine for one account but locks out a second.
2. Most PCs update themselves from the portal through the signed bundle.
3. To move a PC from the older `C:\SmartLab` install, run `Install-CurrentUser.ps1` under each account. It removes old Run entries, the old task and old plain key files, and the PC keeps its card.

## Changing addresses

Edit `site.json`, rebuild with `py tools/pc_agent/make_kit.py`, and re-run the installer. Addresses are not in the scripts.

## Troubleshooting

| Symptom | Likely cause | Action |
|---|---|---|
| "running scripts is disabled" | Execution policy | Use right-click Run with PowerShell. If refused, ask IT |
| "Security software removed the program" | University security | Ask IT. Do not move it elsewhere |
| `FAIL portal REFUSES this key` | Key revoked, or an old backend with two accounts | Deploy the backend, then re-run the installer |
| `this account cannot read the key file` | The file came from another account | Re-run the installer under this account |
| NOTE: another account's agent serves this PC | Two accounts signed in | Normal. It takes over at sign-out |
| Lab PCs say refused | Relay down, or subnet not in `relay_allow` | Check the engineer's PC, then `site.json` |
| No icon | Hidden in the overflow area, or the shell refused it | The agent still works. Check `%TEMP%\smartlab_boot.log` |

Logs: `%TEMP%\smartlab_boot.log`, `smartlab_agent.log`, `smartlab_relay.log`.

## What needs GIU IT

Ask for this if every account on every PC must be covered without each one running the installer:

> Please deploy the Smart Lab PC agent to the Robotics Laboratory PCs for all users, using your software deployment tool. Files: the `lab_usb_kit` folder. Start-up: at user sign-in, `pythonw.exe -E -s <install>\pc_agent\agent_boot.py --config <install>\smartlab.json`. It needs outbound HTTP and HTTPS to the engineer's PC on ports 8000 and 443, and a firewall allow rule for the agent's Python executables. We also ask for your review of the relay on the engineer's PC, which forwards those ports to the isolated Smart Lab network. No inbound access from outside the laboratory is required.
