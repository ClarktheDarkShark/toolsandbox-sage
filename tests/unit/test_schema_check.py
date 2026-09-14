import pytest

from sage_ts.generation.tool_spec import GeneratedTool, ToolFamily, ToolInput, ToolSpec
from sage_ts.validation.schema_check import compile_generated_tool


def _tool(annotation: str, code_annotation: str) -> GeneratedTool:
    return GeneratedTool(
        spec=ToolSpec(
            tool_name="optional_float_helper",
            family=ToolFamily.DERIVED_VALUE_CALCULATOR,
            description="Test helper.",
            inputs=(ToolInput("value", annotation, "Optional float."),),
            output_annotation="dict",
        ),
        code=(
            f"def optional_float_helper(value: {code_annotation}) -> dict:\n"
            "    return {'value': value}\n"
        ),
    )


def test_optional_spec_accepts_plain_base_annotation() -> None:
    result = compile_generated_tool(_tool("float|null", "float"))

    assert result.valid
    assert result.errors == ()


def test_optional_spec_accepts_union_annotation() -> None:
    result = compile_generated_tool(_tool("float|null", "float | None"))

    assert result.valid
    assert result.errors == ()


def test_wrong_annotation_still_rejected() -> None:
    result = compile_generated_tool(_tool("float|null", "str"))

    assert not result.valid
    assert result.errors == ("input_annotation_mismatch:value:str!=float|null",)


def test_undefined_global_name_is_rejected_before_runtime() -> None:
    tool = _tool("float", "float")
    tool = GeneratedTool(
        spec=tool.spec,
        code=(
            "def optional_float_helper(value: float) -> dict:\n"
            "    return {'value': selected_record}\n"
        ),
    )

    result = compile_generated_tool(tool)

    assert not result.valid
    assert result.errors == ("undefined_name:selected_record",)


def test_safe_builtins_and_comprehension_locals_are_not_undefined() -> None:
    tool = GeneratedTool(
        spec=ToolSpec(
            tool_name="sum_visible_values",
            family=ToolFamily.DERIVED_VALUE_CALCULATOR,
            description="Sum visible numeric values.",
            inputs=(ToolInput("values", "list", "Visible values."),),
            output_annotation="dict",
        ),
        code=(
            "def sum_visible_values(values: list) -> dict:\n"
            "    return {'value': sum(int(item) for item in values)}\n"
        ),
    )

    result = compile_generated_tool(tool)

    assert result.valid
    assert result.errors == ()


@pytest.mark.parametrize(
    "signature",
    (
        "def optional_float_helper(value: float, /) -> dict:",
        "def optional_float_helper(value: float, *, debug: bool = False) -> dict:",
        "def optional_float_helper(value: float, *extra) -> dict:",
        "def optional_float_helper(value: float, **kwargs) -> dict:",
    ),
)
def test_non_simple_or_extra_parameters_are_rejected(signature: str) -> None:
    tool = _tool("float", "float")
    tool = GeneratedTool(
        spec=tool.spec,
        code=signature + "\n    return {'value': value}\n",
    )

    result = compile_generated_tool(tool)

    assert not result.valid
    assert len(result.errors) == 1
    assert result.errors[0].startswith("input_signature_mismatch:")
