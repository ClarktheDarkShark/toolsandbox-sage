# SAGE source inventory

This validation-only tool reports the size and symbol structure of the authored
SAGE implementation without counting Apple's native `tool_sandbox/` source or
generated/static run output.

Run it from anywhere inside the repository:

```bash
python validation/inventory/report_inventory.py
python validation/inventory/report_inventory.py --format json --output /tmp/sage-inventory.json
```

The inventory is intentionally based on `git ls-files`, then applies explicit
path rules. This means untracked run output cannot inflate the count, while
tracked files under `artifacts/`, `outputs/`, `dist/`, and `build/` are still
excluded. Dashboard *source* is counted in separate live and Chapter 4
categories; rendered dashboard output is not source.

Both physical LOC and nonblank/non-comment source LOC are reported. Prompt,
policy, contract, example, schema, rule, and catalog text remains in those
totals. Recognizably named external JSON, YAML, Markdown, Jinja, and text prompt
or catalog files are assigned to a separate behavior-catalog category. A
non-additive `behavior_definition` subset makes this content visible so moving
behavior from Python into data files cannot be presented as a real reduction
without separate disclosure.

The tool itself is excluded from the SAGE totals to keep repeated measurements
stable. Its checks run with only the Python standard library:

```bash
python -m unittest discover -s validation/inventory -p 'test_*.py'
```
