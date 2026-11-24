# Laptop hardware audit (read only, 23-24 Nov 2026)
Labels: **V** = measured/read on this laptop, **D** = manufacturer document, **U** = not verified.

| Part | Finding | |
|---|---|---|
| Model | Dell G3 3590, i7-9750H (6 cores), BIOS 1.21.0, Balanced power plan | V |
| GPU | GTX 1650 4 GB, 53 C at idle, 1,141 MiB used | V |
| RAM | 2 x 16 GB DDR4-3200 modules running at 2667, two slots, both full, firmware maximum 32 GB | V |
| Memory use | 9.3 GB free, commit 78 %, paging 0-16 pages/s; largest: Chrome 8.0, Claude 3.1, memory compression 3.0, VS Code 2.2, WSL 2.2 GB | V |
| Pagefile | 24 GB fixed, peak 7.7 GB | V |
| C: | NVMe 512 GB, healthy, about 80-87 GB free of 397 GB; 1,271 MB/s read, 4K 0.14 ms | V |
| D: | Toshiba MQ04ABF100 1 TB hard disk, 843 GB free; 135 MB/s, 4K 10.6 ms (about 75 x slower per small read) | V |
| Docker disk | **on C: now** (`C:/DockerData/disk/docker_data.vhdx`, 43.3 GB, changed 24 Nov 02:27). CLAUDE.md still says D: | V |
| Old Docker folder | `D:/DockerData.bak-20261112` exists; kept, never deleted here | V |
| Disk errors | 128 events in 30 days, all on a removable disk (3-4 and 17-18 Nov) | V |
| Throttling | 0 events id 37 in 30 days; no load test was run | V |
| SSD wear (SMART) | needs administrator; not read | U |
| Internal slots | one M.2 2230/2280 (SATA or NVMe x4), one 2.5" SATA bay | D |
| SATA SSD in the 2.5" bay | same SATA interface; Dell lists hard disks, an SSD is not explicitly confirmed | U |

Dell source: Dell G3 3590 "Setup and Specifications" manual on dell.com. The case was not opened. No load test was run because live
services share the machine.

## Smart Lab value versus personal value
The lab itself uses Docker/WSL, the camera services and the AI models. Chrome and editors used more memory than the whole
Docker VM at the measurement, so closing them during a demo is worth more than any part that can be bought.
