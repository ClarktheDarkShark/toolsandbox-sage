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
