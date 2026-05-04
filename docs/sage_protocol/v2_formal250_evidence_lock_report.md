# V2 Formal 250 Evidence Lock Report

- Updated: `2026-05-04T07:02:15.534203`
- Decision label: `evidence locked`

## Locked Evidence

- Commit hash: `39d5647ee914f00579578c388468819a91c7fd6d`
- Registry path: `artifacts/registry_best3_resolve_select_relative/registry_manifest.json`
- Registry SHA-256: `76de726d25f7f959744704d18a5cf69ff807ca3e3daa7616876e5699ce783caf`
- Frozen claim registry copy: `artifacts/registry_frozen_best3_claim/registry_manifest.json`
- Frozen claim registry SHA-256: `76de726d25f7f959744704d18a5cf69ff807ca3e3daa7616876e5699ce783caf`
- Formal 250 manifest: `artifacts/summaries/v2_formal250_clean_20260504_034104/cohort_manifest.json`
- Formal 250 manifest SHA-256: `c7ec4010f8fc3ea3ca1f914b8d5a980f70e51494c75cc3d9f9148b0b3604a47e`
- Summary JSON: `artifacts/summaries/v2_final_best3_formal_validation/summary.json`
- Summary JSON SHA-256: `c625520913b0ffb998cb308542196c067f6e0aba29bf9ad5dbf4fd58616668ec`
- Protocol manifest: `outputs/v2_formal250_clean_20260504_034104_frozen_best3_relative_20260504_052217/validate_250_20260504_052222/protocol_manifest.json`
- Protocol manifest SHA-256: `cd759bddc93823c9295ca3291ef59d5327c72b314de7114a891b4c68768e9e09`
- Paired comparison: `outputs/v2_formal250_clean_20260504_034104_frozen_best3_relative_20260504_052217/validate_250_20260504_052222/paired_comparison.json`
- Paired comparison SHA-256: `8c967688a806ef276419d40a51fded941af13f5de9a5519714c560d5e0bb8f80`
- Helper contribution summary: `outputs/v2_formal250_clean_20260504_034104_frozen_best3_relative_20260504_052217/validate_250_20260504_052222/helper_contribution_summary.json`
- Helper contribution SHA-256: `62379a81870182ef35a4369cc1f07beffa44f8160c5f2525a3db478a68ab2ed1`
- Dashboard: `http://127.0.0.1:5520/outputs/v2_formal250_clean_20260504_034104_frozen_best3_relative_20260504_052217/validate_250_20260504_052222/dashboard/index.html`
- Task focus dashboard: `http://127.0.0.1:5520/outputs/v2_formal250_clean_20260504_034104_frozen_best3_relative_20260504_052217/validate_250_20260504_052222/dashboard/task_focus.html`

## Run Conditions

- Exact command: `conda run -n lifelong bash -lc 'export PYTHONPATH=src:.; export SAGE_V2_EXPERIMENT_FEATURES=default; python scripts/run_sage_protocol.py --manifest artifacts/summaries/v2_formal250_clean_20260504_034104/cohort_manifest.json --mode validate_250 --registry-dir artifacts/registry_candidates/v2_formal250_clean_20260504_034104_frozen_best3_relative_20260504_052217 --output-root outputs/v2_formal250_clean_20260504_034104_frozen_best3_relative_20260504_052217 --artifact-root artifacts --generation off --parallel-arms --control-cache use-if-eligible'`
- Generation enabled: `False`
- Registry digest before run: `76de726d25f7f959744704d18a5cf69ff807ca3e3daa7616876e5699ce783caf`
- Registry digest after run: `76de726d25f7f959744704d18a5cf69ff807ca3e3daa7616876e5699ce783caf`
- Control cache mode/source: `use-if-eligible` / `fresh`
- Cached/fresh controls: `0` / `250`
- Cohort quality gate: `pass`
- Cohort quality failures: `[]`
- Runtime exceptions: `0`
- Helper side-effect incidents: `0`

Decision label: `evidence locked`
