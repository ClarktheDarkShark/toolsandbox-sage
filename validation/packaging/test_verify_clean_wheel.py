from __future__ import annotations

from pathlib import Path
import tempfile
import unittest
import zipfile

from validation.packaging.verify_clean_wheel import (
    REQUIRED_ENTRY_POINTS,
    VerificationError,
    compare_application_payload,
    derive_application_payload,
    inspect_wheel,
    verify_entry_points,
)


class DeriveApplicationPayloadTest(unittest.TestCase):
    def test_derives_names_and_bytes_from_package_configuration(self) -> None:
        archive = {
            "pyproject.toml": b"""
[tool.setuptools.packages.find]
where = [".", "src"]
include = ["native*", "sage*"]
exclude = ["src*"]
namespaces = false

[tool.setuptools.package-data]
"sage.dashboard" = ["*.html"]
""",
            "native/__init__.py": b"native init\n",
            "native/tool.py": b"native tool\n",
            "native/ignored.txt": b"not package data\n",
            "src/sage/__init__.py": b"sage init\n",
            "src/sage/core.py": b"sage core\n",
            "src/sage/dashboard/__init__.py": b"dashboard init\n",
            "src/sage/dashboard/index.html": b"<html></html>\n",
            "src/not_a_package/stray.py": b"stray\n",
            "README.md": b"readme\n",
        }

        payload = derive_application_payload(archive)

        self.assertEqual(
            payload,
            {
                "native/__init__.py": b"native init\n",
                "native/tool.py": b"native tool\n",
                "sage/__init__.py": b"sage init\n",
                "sage/core.py": b"sage core\n",
                "sage/dashboard/__init__.py": b"dashboard init\n",
                "sage/dashboard/index.html": b"<html></html>\n",
            },
        )


class WheelInspectionTest(unittest.TestCase):
    def test_reads_payload_and_exact_entry_points(self) -> None:
        entries = "[console_scripts]\n" + "".join(
            f"{name} = {value}\n" for name, value in REQUIRED_ENTRY_POINTS.items()
        )
        with tempfile.TemporaryDirectory() as temporary:
            wheel = Path(temporary) / "fixture.whl"
            with zipfile.ZipFile(wheel, "w") as bundle:
                bundle.writestr("sage_ts/__init__.py", b"fixture\n")
                bundle.writestr(
                    "toolsandbox_sage-0.1.0.dist-info/entry_points.txt", entries
                )
                bundle.writestr("toolsandbox_sage-0.1.0.dist-info/METADATA", b"x\n")

            payload, entry_points = inspect_wheel(wheel)

        self.assertEqual(payload, {"sage_ts/__init__.py": b"fixture\n"})
        verify_entry_points(entry_points)

    def test_rejects_an_extra_application_file(self) -> None:
        with self.assertRaisesRegex(VerificationError, "unexpected"):
            compare_application_payload(
                {"sage_ts/__init__.py": b"expected\n"},
                {
                    "sage_ts/__init__.py": b"expected\n",
                    "sage_ts/stale.py": b"stale\n",
                },
            )

    def test_rejects_changed_committed_bytes(self) -> None:
        with self.assertRaisesRegex(VerificationError, "changed"):
            compare_application_payload(
                {"sage_ts/__init__.py": b"expected\n"},
                {"sage_ts/__init__.py": b"changed\n"},
            )

    def test_rejects_any_entry_point_difference(self) -> None:
        changed = dict(REQUIRED_ENTRY_POINTS)
        changed["sage-dashboard"] = "wrong.module:main"
        with self.assertRaisesRegex(VerificationError, "entry points differ"):
            verify_entry_points(changed)


if __name__ == "__main__":
    unittest.main()
