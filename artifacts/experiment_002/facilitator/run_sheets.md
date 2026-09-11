# Facilitator run sheets

Study seed `20260911`. Assignment is counterbalanced and between-subject: no participant sees the same incident twice.

**These sheets do not name telemetry conditions, on purpose.** The mapping exists in `private/condition_map.json`. Do not open it during a session, and do not open it at all if you can avoid it until scoring is done.

Before the first session, read HUMAN_STUDY_GUIDE.md. During a session, give the participant only their own folder under `packets/<participant>/`.

## Order of work

| participant | 1 | 2 | 3 | 4 | 5 | 6 |
| --- | --- | --- | --- | --- | --- | --- |
| P1 | case_06 | case_04 | case_01 | case_05 | case_02 | case_03 |
| P2 | case_06 | case_03 | case_02 | case_01 | case_05 | case_04 |
| P3 | case_05 | case_03 | case_01 | case_06 | case_04 | case_02 |
| P4 | case_02 | case_05 | case_03 | case_04 | case_06 | case_01 |

## P1

Hand over: `artifacts/experiment_002/packets/P1/`

| # | folder | when they open it | when they hand it back |
| --- | --- | --- | --- |
| 1 | `01_case_06_packet_3QYH` | `python -m experiment2 start --participant P1 --packet case_06_packet_3QYH` | `python -m experiment2 submit --participant P1 --answers <file>` |
| 2 | `02_case_04_packet_WCM6` | `python -m experiment2 start --participant P1 --packet case_04_packet_WCM6` | `python -m experiment2 submit --participant P1 --answers <file>` |
| 3 | `03_case_01_packet_XNGX` | `python -m experiment2 start --participant P1 --packet case_01_packet_XNGX` | `python -m experiment2 submit --participant P1 --answers <file>` |
| 4 | `04_case_05_packet_LNGU` | `python -m experiment2 start --participant P1 --packet case_05_packet_LNGU` | `python -m experiment2 submit --participant P1 --answers <file>` |
| 5 | `05_case_02_packet_JHR7` | `python -m experiment2 start --participant P1 --packet case_02_packet_JHR7` | `python -m experiment2 submit --participant P1 --answers <file>` |
| 6 | `06_case_03_packet_T3AC` | `python -m experiment2 start --participant P1 --packet case_03_packet_T3AC` | `python -m experiment2 submit --participant P1 --answers <file>` |

After the last case, ask and write into `responses/P1/exit_notes.md`:

1. Did you notice differences between the packages? What did you make of them?
2. Did you develop a rule of thumb as you went? What was it?
3. Had you seen any of these incidents before?

## P2

Hand over: `artifacts/experiment_002/packets/P2/`

| # | folder | when they open it | when they hand it back |
| --- | --- | --- | --- |
| 1 | `01_case_06_packet_KJUF` | `python -m experiment2 start --participant P2 --packet case_06_packet_KJUF` | `python -m experiment2 submit --participant P2 --answers <file>` |
| 2 | `02_case_03_packet_PMKY` | `python -m experiment2 start --participant P2 --packet case_03_packet_PMKY` | `python -m experiment2 submit --participant P2 --answers <file>` |
| 3 | `03_case_02_packet_9JAN` | `python -m experiment2 start --participant P2 --packet case_02_packet_9JAN` | `python -m experiment2 submit --participant P2 --answers <file>` |
| 4 | `04_case_01_packet_JJ6N` | `python -m experiment2 start --participant P2 --packet case_01_packet_JJ6N` | `python -m experiment2 submit --participant P2 --answers <file>` |
| 5 | `05_case_05_packet_FAMX` | `python -m experiment2 start --participant P2 --packet case_05_packet_FAMX` | `python -m experiment2 submit --participant P2 --answers <file>` |
| 6 | `06_case_04_packet_E69F` | `python -m experiment2 start --participant P2 --packet case_04_packet_E69F` | `python -m experiment2 submit --participant P2 --answers <file>` |

After the last case, ask and write into `responses/P2/exit_notes.md`:

1. Did you notice differences between the packages? What did you make of them?
2. Did you develop a rule of thumb as you went? What was it?
3. Had you seen any of these incidents before?

## P3

Hand over: `artifacts/experiment_002/packets/P3/`

| # | folder | when they open it | when they hand it back |
| --- | --- | --- | --- |
| 1 | `01_case_05_packet_LNGU` | `python -m experiment2 start --participant P3 --packet case_05_packet_LNGU` | `python -m experiment2 submit --participant P3 --answers <file>` |
| 2 | `02_case_03_packet_T3AC` | `python -m experiment2 start --participant P3 --packet case_03_packet_T3AC` | `python -m experiment2 submit --participant P3 --answers <file>` |
| 3 | `03_case_01_packet_XNGX` | `python -m experiment2 start --participant P3 --packet case_01_packet_XNGX` | `python -m experiment2 submit --participant P3 --answers <file>` |
| 4 | `04_case_06_packet_3QYH` | `python -m experiment2 start --participant P3 --packet case_06_packet_3QYH` | `python -m experiment2 submit --participant P3 --answers <file>` |
| 5 | `05_case_04_packet_WCM6` | `python -m experiment2 start --participant P3 --packet case_04_packet_WCM6` | `python -m experiment2 submit --participant P3 --answers <file>` |
| 6 | `06_case_02_packet_JHR7` | `python -m experiment2 start --participant P3 --packet case_02_packet_JHR7` | `python -m experiment2 submit --participant P3 --answers <file>` |

After the last case, ask and write into `responses/P3/exit_notes.md`:

1. Did you notice differences between the packages? What did you make of them?
2. Did you develop a rule of thumb as you went? What was it?
3. Had you seen any of these incidents before?

## P4

Hand over: `artifacts/experiment_002/packets/P4/`

| # | folder | when they open it | when they hand it back |
| --- | --- | --- | --- |
| 1 | `01_case_02_packet_9JAN` | `python -m experiment2 start --participant P4 --packet case_02_packet_9JAN` | `python -m experiment2 submit --participant P4 --answers <file>` |
| 2 | `02_case_05_packet_FAMX` | `python -m experiment2 start --participant P4 --packet case_05_packet_FAMX` | `python -m experiment2 submit --participant P4 --answers <file>` |
| 3 | `03_case_03_packet_PMKY` | `python -m experiment2 start --participant P4 --packet case_03_packet_PMKY` | `python -m experiment2 submit --participant P4 --answers <file>` |
| 4 | `04_case_04_packet_E69F` | `python -m experiment2 start --participant P4 --packet case_04_packet_E69F` | `python -m experiment2 submit --participant P4 --answers <file>` |
| 5 | `05_case_06_packet_KJUF` | `python -m experiment2 start --participant P4 --packet case_06_packet_KJUF` | `python -m experiment2 submit --participant P4 --answers <file>` |
| 6 | `06_case_01_packet_JJ6N` | `python -m experiment2 start --participant P4 --packet case_01_packet_JJ6N` | `python -m experiment2 submit --participant P4 --answers <file>` |

After the last case, ask and write into `responses/P4/exit_notes.md`:

1. Did you notice differences between the packages? What did you make of them?
2. Did you develop a rule of thumb as you went? What was it?
3. Had you seen any of these incidents before?
