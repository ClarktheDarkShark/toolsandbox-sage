from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path, PurePosixPath

from report_inventory import build_inventory, classify_path


class InventoryTest(unittest.TestCase):
    def test_classification_guards_static_and_native_content(self) -> None:
        category, reason = classify_path(PurePosixPath("tool_sandbox/tools/contact.py"))
        self.assertIsNone(category)
        self.assertEqual(reason, "native_toolsandbox")

        category, reason = classify_path(
            PurePosixPath("artifacts/run/dashboard/task_compare.html")
        )
        self.assertIsNone(category)
        self.assertEqual(reason, "generated_or_static_output")

        category, reason = classify_path(
            PurePosixPath("validation/contract/frozen_behavior_contract.json")
        )
        self.assertIsNone(category)
        self.assertEqual(reason, "validation_tooling")

        category, reason = classify_path(
            PurePosixPath("src/sage_ts/dashboard/task_compare_template.py")
        )
        self.assertEqual(category.key, "live_dashboard")
        self.assertIsNone(reason)

    def test_inventory_uses_tracked_files_and_counts_behavior_text(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            files = {
                "src/sage_ts/generation/tool_generator.py": (
                    "POLICY_RULES = ('keep this catalog',)\n\n"
                    "def generation_prompt():\n"
                    "    return (\n"
                    "        'This prompt controls generated tool behavior and is deliberately '\n"
                    "        'long enough to span source lines.'\n"
                    "    )\n"
                ),
                "src/sage_ts/dashboard/template.py": "DASHBOARD_HTML = '<html></html>'\n",
                "tool_sandbox/tools/native.py": "def native():\n    return True\n",
                "artifacts/run/dashboard.html": "<html>generated</html>\n",
                "prompts/tool_policy_catalog.yaml": "policy: keep-this-visible\n",
                "outputs/untracked/result.json": "{}\n",
            }
            for relative, text in files.items():
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(text, encoding="utf-8")
            subprocess.run(
                [
                    "git",
                    "-C",
                    str(root),
                    "add",
                    "src",
                    "tool_sandbox",
                    "artifacts",
                    "prompts",
                ],
                check=True,
            )

            inventory = build_inventory(root)
            totals = inventory["totals"]
            self.assertEqual(totals["tracked_source_file_count"], 3)
            self.assertGreaterEqual(totals["behavior_definition_source_subset"], 3)
            self.assertEqual(totals["function_count"], 1)
            self.assertEqual(
                inventory["exclusions"]["file_count_by_reason"]["native_toolsandbox"],
                1,
            )
            behavior_categories = {
                row["key"]: row for row in inventory["categories"]
            }
            self.assertEqual(
                behavior_categories["behavior_catalogs"][
                    "behavior_definition_source_lines"
                ],
                1,
            )
            self.assertEqual(
                inventory["exclusions"]["file_count_by_reason"][
                    "generated_or_static_output"
                ],
                1,
            )
            excluded_paths = {
                item["path"] for item in inventory["exclusions"]["files"]
            }
            self.assertNotIn("outputs/untracked/result.json", excluded_paths)


if __name__ == "__main__":
    unittest.main()
