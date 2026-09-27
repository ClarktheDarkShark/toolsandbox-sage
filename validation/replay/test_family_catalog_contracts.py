from __future__ import annotations

from collections import OrderedDict

from validation.replay.family_catalog_contracts import _lookup, _typed


def test_typed_preserves_nested_container_types_and_mapping_order() -> None:
    value = OrderedDict(
        (
            ("second", (1, 2)),
            ("first", [True, None]),
        )
    )

    result = _typed(value)

    assert result["python_type"] == "OrderedDict"
    assert [item["key"]["value"] for item in result["items"]] == [
        "second",
        "first",
    ]
    assert result["items"][0]["value"]["python_type"] == "tuple"
    assert result["items"][1]["value"]["python_type"] == "list"


def test_lookup_distinguishes_missing_none_and_empty_tuple() -> None:
    mapping = {"none": None, "empty": ()}

    assert _lookup(mapping, "missing") == {"present": False}
    assert _lookup(mapping, "none") == {
        "present": True,
        "value": {"python_type": "NoneType", "value": None},
    }
    assert _lookup(mapping, "empty") == {
        "present": True,
        "value": {"python_type": "tuple", "items": []},
    }
