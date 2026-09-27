from __future__ import annotations

import hashlib
from pathlib import Path
import tempfile
import unittest

from validation.replay.compare import ACTOR_SOURCE_PATH, _actor_source_identity


class ActorSourceIdentityTest(unittest.TestCase):
    def test_hashes_both_actor_sources(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            reference_root = root / "reference"
            candidate_root = root / "candidate"
            reference_actor = reference_root / ACTOR_SOURCE_PATH
            candidate_actor = candidate_root / ACTOR_SOURCE_PATH
            reference_actor.parent.mkdir(parents=True)
            candidate_actor.parent.mkdir(parents=True)
            reference_actor.write_bytes(b"reference actor\n")
            candidate_actor.write_bytes(b"candidate actor\n")

            identity = _actor_source_identity(reference_root, candidate_root)

        self.assertEqual(
            identity,
            {
                "path": ACTOR_SOURCE_PATH.as_posix(),
                "reference_sha256": hashlib.sha256(b"reference actor\n").hexdigest(),
                "candidate_sha256": hashlib.sha256(b"candidate actor\n").hexdigest(),
            },
        )

    def test_missing_actor_source_fails_instead_of_emitting_identity(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)

            with self.assertRaises(FileNotFoundError):
                _actor_source_identity(root / "reference", root / "candidate")


if __name__ == "__main__":
    unittest.main()
