from sage_ts.config.gap_closure_lab import (
    _hashable_manifest,
    make_gap_closure_lab_manifest,
    payload_sha256,
)


def test_gap_closure_lab_splits_are_disjoint_and_sized() -> None:
    manifest = make_gap_closure_lab_manifest()

    assert manifest["split_sizes"] == {
        "seed_dev_labeled": 8,
        "pilot_unseen": 20,
        "expanded_pilot_unseen": 60,
        "confirm_unseen": 100,
        "scale_unseen": 250,
    }
    scenario_ids = [
        row["scenario_id"] for rows in manifest["splits"].values() for row in rows
    ]
    assert len(scenario_ids) == len(set(scenario_ids))


def test_gap_closure_lab_label_policy_is_explicit() -> None:
    manifest = make_gap_closure_lab_manifest()

    seed_rows = manifest["splits"]["seed_dev_labeled"]
    unseen_rows = [
        row
        for split_name in (
            "pilot_unseen",
            "expanded_pilot_unseen",
            "confirm_unseen",
            "scale_unseen",
        )
        for row in manifest["splits"][split_name]
    ]
    assert all(row["truth_labels_inspected"] for row in seed_rows)
    assert all(not row["truth_labels_inspected"] for row in unseen_rows)
    assert not any(row["used_for_final_evaluation"] for row in seed_rows)
    assert all(
        row["used_for_final_evaluation"] for row in manifest["splits"]["scale_unseen"]
    )


def test_seed_dev_families_are_excluded_from_unseen_splits() -> None:
    manifest = make_gap_closure_lab_manifest()

    seed_families = {
        row["family_label"] for row in manifest["splits"]["seed_dev_labeled"]
    }
    unseen_families = {
        row["family_label"]
        for split_name in (
            "pilot_unseen",
            "expanded_pilot_unseen",
            "confirm_unseen",
            "scale_unseen",
        )
        for row in manifest["splits"][split_name]
    }
    assert seed_families.isdisjoint(unseen_families)


def test_gap_closure_lab_manifest_has_runner_aliases() -> None:
    manifest = make_gap_closure_lab_manifest()

    assert manifest["split_aliases"] == {
        "pilot_20": "pilot_unseen",
        "expanded_60": "expanded_pilot_unseen",
        "confirm_100": "confirm_unseen",
        "validate_250": "scale_unseen",
        "promotion_250": "scale_unseen",
    }


def test_gap_closure_lab_manifest_payload_hash_is_stable() -> None:
    manifest = make_gap_closure_lab_manifest()

    assert manifest["manifest_integrity"]["payload_sha256"] == payload_sha256(
        _hashable_manifest(manifest)
    )


def test_gap_closure_lab_manifest_rows_are_canonicalized() -> None:
    manifest = make_gap_closure_lab_manifest()

    for rows in manifest["splits"].values():
        for row in rows:
            assert row["categories"] == sorted(row["categories"])
