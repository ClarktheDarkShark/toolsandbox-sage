"""Task-stratum classification for ToolSandbox SAGE coverage audits."""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Iterable
from typing import Any

STRATA = (
    "temporal_reminder_date_canonicalization",
    "contact_message_search_disambiguation",
    "record_filtering_ranking_latest_selection",
    "direct_state_precondition_service_enablement",
    "holiday_calendar_business_day_logic",
    "stock_market_numeric_normalization",
    "weather_location_current_city_distance",
    "generic_multi_tool_composition",
    "insufficient_information_clarification",
    "other_uncovered_clusters",
)


HELPER_TRIGGERS: dict[str, tuple[str, ...]] = {
    "days_between_timestamps": ("holiday_calendar_business_day_logic",),
    "relative_day_time_to_timestamp": ("temporal_reminder_date_canonicalization",),
    "recency_to_timestamp_bounds": (
        "temporal_reminder_date_canonicalization",
        "record_filtering_ranking_latest_selection",
    ),
    "resolve_search_window_or_bounds": (
        "temporal_reminder_date_canonicalization",
        "record_filtering_ranking_latest_selection",
        "contact_message_search_disambiguation",
    ),
    "select_latest_record_by_timestamp": (
        "record_filtering_ranking_latest_selection",
        "contact_message_search_disambiguation",
    ),
    "select_record_by_timestamp_extreme": (
        "record_filtering_ranking_latest_selection",
        "contact_message_search_disambiguation",
    ),
    "select_visible_record_by_constraints": (
        "contact_message_search_disambiguation",
        "record_filtering_ranking_latest_selection",
    ),
    "select_action_target_by_recency": (
        "record_filtering_ranking_latest_selection",
        "contact_message_search_disambiguation",
        "temporal_reminder_date_canonicalization",
    ),
    "prepare_side_effect_args_from_selected_record": (
        "generic_multi_tool_composition",
        "contact_message_search_disambiguation",
        "record_filtering_ranking_latest_selection",
    ),
    "constraint_to_action_planner": (
        "generic_multi_tool_composition",
        "contact_message_search_disambiguation",
        "record_filtering_ranking_latest_selection",
    ),
    "next_service_tool_call": ("direct_state_precondition_service_enablement",),
    "recover_from_tool_error": ("direct_state_precondition_service_enablement",),
    "next_service_enablement_action": ("direct_state_precondition_service_enablement",),
    "prepare_reminder_creation_args": (
        "temporal_reminder_date_canonicalization",
        "generic_multi_tool_composition",
    ),
    "extract_service_answer_field": ("weather_location_current_city_distance",),
    "plan_contact_lookup_query": (
        "contact_message_search_disambiguation",
        "generic_multi_tool_composition",
    ),
    "plan_contact_relationship_batch_update": (
        "contact_message_search_disambiguation",
        "generic_multi_tool_composition",
    ),
    "plan_contact_update_from_id": (
        "contact_message_search_disambiguation",
        "generic_multi_tool_composition",
    ),
    "prepare_safe_action_or_abstain": (
        "insufficient_information_clarification",
        "generic_multi_tool_composition",
    ),
    "extract_contact_field_from_search_result": (
        "contact_message_search_disambiguation",
    ),
}

OPPORTUNITY_HELPERS: dict[str, tuple[str, ...]] = {
    "canonicalizer:relative_day_time_timestamp": ("relative_day_time_to_timestamp",),
    "derived_value:days_between_timestamps": ("days_between_timestamps",),
    "derived_value:extract_service_answer_field": ("extract_service_answer_field",),
    "derived_value:recency_timestamp_bounds": ("recency_to_timestamp_bounds",),
    "derived_value:resolve_search_window_or_bounds": (
        "resolve_search_window_or_bounds",
    ),
    "search_filter:select_record_by_timestamp_extreme": (
        "select_record_by_timestamp_extreme",
    ),
    "search_filter:select_contact_field_by_constraint": (
        "select_contact_field_by_constraint",
    ),
    "composite:plan_contact_lookup_query": ("plan_contact_lookup_query",),
    "composite:plan_contact_relationship_batch_update": (
        "plan_contact_relationship_batch_update",
    ),
    "composite:plan_contact_update_from_id": ("plan_contact_update_from_id",),
    "validation:prepare_safe_action_or_abstain": ("prepare_safe_action_or_abstain",),
    "derived_value:extract_contact_field_from_search_result": (
        "extract_contact_field_from_search_result",
    ),
    "search_filter:select_visible_record_by_constraints": (
        "select_visible_record_by_constraints",
    ),
    "search_filter:select_action_target_by_recency": (
        "select_action_target_by_recency",
    ),
    "composite:prepare_side_effect_args_from_selected_record": (
        "prepare_side_effect_args_from_selected_record",
    ),
    "composite:constraint_to_action_planner": ("constraint_to_action_planner",),
    "state_precondition:next_service_tool_call": ("next_service_tool_call",),
    "state_precondition:recover_from_tool_error": ("recover_from_tool_error",),
    "composite:prepare_reminder_creation_args": ("prepare_reminder_creation_args",),
}

VARIANT_SUFFIXES = (
    "_arg_description_scrambled",
    "_arg_type_scrambled",
    "_tool_description_scrambled",
    "_tool_name_scrambled",
    "_10_distraction_tools",
    "_3_distraction_tools",
    "_all_tools",
)

EXTERNAL_SERVICE_TOKENS = (
    "weather",
    "temperature",
    "current_city",
    "distance",
    "lat_lon",
    "current_location",
    "location_name",
    "location_around",
    "address",
    "stock",
    "market",
    "price",
    "currency",
    "convert_currency",
    "exchange_rate",
)

DIRECT_SERVICE_HELPER_PREFIXES = (
    "turn_on_wifi_low_battery_mode",
    "turn_on_cellular_low_battery_mode",
    "turn_on_location_low_battery_mode",
)

DOWNSTREAM_SERVICE_HELPER_PREFIXES = (
    "add_reminder_content_and_week_delta_and_time_and_location_low_battery_mode",
    "find_current_city_low_battery_mode",
    "find_distance_with_location_name_low_battery_mode",
    "find_stock_symbol_with_company_name_low_battery_mode",
    "find_temperature_f_with_location_and_time_diff_low_battery_mode",
    "find_temperature_low_battery_mode",
)

VISIBLE_RECORD_CONSTRAINT_PREFIXES = (
    "remove_contact_by_phone",
    "search_phone_number_with_name",
    "search_relationship_with_phone_number",
    "search_sender_phone_number_with_content",
    "update_contact_relationship_with_relationship",
    "search_name_with_relationship",
)

ACTION_TARGET_PREFIXES = (
    "modify_contact_with_message_recency",
    "modify_reminder_with_recency_latest",
    "remove_reminder_with_recency_latest",
)

SIDE_EFFECT_PREP_PREFIXES = (
    "remove_contact_by_phone",
    "update_contact_relationship_with_relationship",
    "modify_contact_with_message_recency",
    "modify_reminder_with_recency_latest",
    "remove_reminder_with_recency_latest",
)


def base_task_family(scenario_name: str) -> str:
    """Collapse ToolSandbox robustness variants into a base task family."""
    family = scenario_name
    changed = True
    while changed:
        changed = False
        for suffix in VARIANT_SUFFIXES:
            if family.endswith(suffix):
                family = family[: -len(suffix)]
                changed = True
    family = re.sub(r"_multiple_user_turn", "", family)
    family = re.sub(r"_ambiguous", "", family)
    if family.endswith("_alt"):
        family = family[:-4]
    return family


def classify_task_strata(
    scenario_name: str,
    categories: Iterable[str] | None = None,
) -> list[str]:
    """Return all task strata that materially describe a scenario."""

    name = scenario_name.lower()
    category_set = {category.upper() for category in categories or ()}
    strata: list[str] = []

    has_reminder = "reminder" in name
    has_message = "message" in name
    has_contact = any(
        token in name
        for token in (
            "contact",
            "phone_number",
            "relationship",
            "sender",
            "recipient",
        )
    )
    has_temporal_language = any(
        token in name
        for token in (
            "recency",
            "yesterday",
            "tomorrow",
            "upcoming",
            "latest",
            "oldest",
            "date",
            "time",
            "week_delta",
            "weekday_delta",
        )
    )
    if has_reminder and has_temporal_language:
        strata.append("temporal_reminder_date_canonicalization")

    if has_contact or has_message:
        strata.append("contact_message_search_disambiguation")

    if any(
        token in name
        for token in (
            "latest",
            "oldest",
            "recency",
            "search_",
            "find_",
            "filter",
            "rank",
        )
    ):
        strata.append("record_filtering_ranking_latest_selection")

    if (
        any(
            token in name
            for token in (
                "wifi",
                "cellular",
                "low_battery",
                "turn_on_location",
                "location_service",
                "service",
            )
        )
        or "STATE_DEPENDENCY" in category_set
    ):
        strata.append("direct_state_precondition_service_enablement")

    if any(token in name for token in ("holiday", "calendar", "business_day")):
        strata.append("holiday_calendar_business_day_logic")

    if any(token in name for token in ("stock", "market", "price")):
        strata.append("stock_market_numeric_normalization")

    if any(
        token in name
        for token in (
            "weather",
            "temperature",
            "distance",
            "current_city",
            "address",
            "lat_lon",
            "location_name",
        )
    ):
        strata.append("weather_location_current_city_distance")

    if (
        "MULTIPLE_TOOL_CALL" in category_set
        or "MULTIPLE_USER_TURN" in category_set
        or "multiple_user_turn" in name
        or "all_tools" in name
        or "distraction_tools" in name
    ):
        strata.append("generic_multi_tool_composition")

    if "INSUFFICIENT_INFORMATION" in category_set or "insufficient_information" in name:
        strata.append("insufficient_information_clarification")

    if not strata:
        strata.append("other_uncovered_clusters")

    return strata


def expected_helper_fit(
    scenario_name: str, categories: Iterable[str] | None = None
) -> list[str]:
    """Estimate which current retained helpers could plausibly apply."""

    name = scenario_name.lower()
    strata = set(classify_task_strata(scenario_name, categories))
    helpers: list[str] = []

    if "insufficient_information" not in name and (
        (
            "temporal_reminder_date_canonicalization" in strata
            and any(
                token in name
                for token in ("date", "time", "week_delta", "weekday_delta")
            )
        )
        or name.startswith("modify_reminder_with_recency_latest")
    ):
        helpers.append("relative_day_time_to_timestamp")

    bounded_recency = any(token in name for token in ("yesterday", "today", "upcoming"))
    if (
        "insufficient_information" not in name
        and bounded_recency
        and ("creation_recency" in name or "message" in name)
    ):
        helpers.append("recency_to_timestamp_bounds")

    if (
        "insufficient_information" not in name
        and name.startswith("search_reminder_with_creation_recency_")
        and any(token in name for token in ("yesterday", "today"))
    ):
        helpers.append("resolve_search_window_or_bounds")
    if (
        "insufficient_information" not in name
        and name.startswith("search_reminder_with_recency_")
        and any(token in name for token in ("yesterday", "today", "upcoming"))
    ):
        helpers.append("resolve_search_window_or_bounds")
    if "insufficient_information" not in name and name.startswith(
        (
            "modify_contact_with_message_recency",
            "search_message_with_recency_latest",
            "search_message_with_recency_oldest",
            "remove_reminder_with_recency_latest",
        )
    ):
        helpers.append("select_record_by_timestamp_extreme")
    if "insufficient_information" not in name and name.startswith(
        (
            "modify_contact_with_message_recency",
            "modify_reminder_with_recency_latest",
            "remove_reminder_with_recency_latest",
            "search_message_with_recency_latest",
            "search_message_with_recency_oldest",
        )
    ):
        helpers.append("resolve_search_window_or_bounds")
    if any(token in name for token in ("holiday", "business_day")):
        helpers.append("days_between_timestamps")
    if "insufficient_information" not in name and name.startswith(
        (
            "search_name_with_relationship",
            "search_phone_number_with_name",
            "search_relationship_with_phone_number",
        )
    ):
        helpers.append("plan_contact_lookup_query")
        helpers.append("extract_contact_field_from_search_result")
    if "insufficient_information" not in name and name.startswith(
        "update_contact_relationship_with_relationship"
    ):
        helpers.append("plan_contact_relationship_batch_update")
    if "insufficient_information" not in name and name.startswith(
        "update_contact_with_id_and_phone_number"
    ):
        helpers.append("plan_contact_update_from_id")
    if "insufficient_information" in name:
        helpers.append("prepare_safe_action_or_abstain")
    return helpers


def expected_birth_opportunities(
    scenario_name: str,
    categories: Iterable[str] | None = None,
) -> list[str]:
    """Estimate narrow adequacy-gate patterns that can currently birth a helper."""

    name = scenario_name.lower()
    category_set = {category.upper() for category in categories or ()}
    if "INSUFFICIENT_INFORMATION" in category_set or "insufficient_information" in name:
        return ["validation:prepare_safe_action_or_abstain"]

    opportunities: list[str] = []
    if "recency" in name and "CANONICALIZATION" in category_set:
        opportunities.append("derived_value:recency_timestamp_bounds")
    if name.startswith("search_reminder_with_creation_recency_") and any(
        token in name for token in ("yesterday", "today")
    ):
        opportunities.append("derived_value:resolve_search_window_or_bounds")
    if name.startswith("search_reminder_with_recency_") and any(
        token in name for token in ("yesterday", "today", "upcoming")
    ):
        opportunities.append("derived_value:resolve_search_window_or_bounds")
    if name.startswith("modify_reminder_with_recency_latest"):
        opportunities.append("canonicalizer:relative_day_time_timestamp")
        opportunities.append("derived_value:resolve_search_window_or_bounds")
    if name.startswith("remove_reminder_with_recency_latest"):
        opportunities.append("search_filter:select_record_by_timestamp_extreme")
        opportunities.append("derived_value:resolve_search_window_or_bounds")
    if name.startswith(
        (
            "modify_contact_with_message_recency",
            "search_message_with_recency_latest",
            "search_message_with_recency_oldest",
        )
    ):
        opportunities.append("search_filter:select_record_by_timestamp_extreme")
        opportunities.append("derived_value:resolve_search_window_or_bounds")
    # Do not count bounds-only message window helpers as claim-grade birth
    # opportunities; latest/oldest failures need selection/action helpers.
    scalar_contact_lookup = name.startswith(
        (
            "search_name_with_relationship",
            "search_phone_number_with_name",
            "search_relationship_with_phone_number",
        )
    )
    relationship_batch_update = name.startswith(
        "update_contact_relationship_with_relationship"
    )
    if (
        "ambiguous" not in name
        and "insufficient_information" not in name
        and name.startswith(VISIBLE_RECORD_CONSTRAINT_PREFIXES)
        and not scalar_contact_lookup
        and not relationship_batch_update
    ):
        opportunities.append("search_filter:select_visible_record_by_constraints")
    if "insufficient_information" not in name and name.startswith(
        ACTION_TARGET_PREFIXES
    ):
        opportunities.append("search_filter:select_action_target_by_recency")
    if (
        "ambiguous" not in name
        and "insufficient_information" not in name
        and name.startswith(SIDE_EFFECT_PREP_PREFIXES)
    ):
        opportunities.append("composite:prepare_side_effect_args_from_selected_record")
    if "ambiguous" not in name and "insufficient_information" not in name:
        if scalar_contact_lookup:
            opportunities.append("composite:plan_contact_lookup_query")
        if relationship_batch_update:
            opportunities.append("composite:plan_contact_relationship_batch_update")
        if name.startswith("update_contact_with_id_and_phone_number"):
            opportunities.append("composite:plan_contact_update_from_id")
    if (
        "ambiguous" not in name
        and "insufficient_information" not in name
        and name.startswith(
            (
                "remove_contact_by_phone",
                "search_sender_phone_number_with_content",
            )
        )
    ):
        opportunities.append("composite:plan_contact_lookup_query")
        opportunities.append("derived_value:extract_contact_field_from_search_result")
        opportunities.append("composite:constraint_to_action_planner")
    if name.startswith("find_days_till_holiday"):
        opportunities.append("derived_value:days_between_timestamps")
    if name.startswith("find_stock_symbol_with_company_name"):
        opportunities.append("derived_value:extract_stock_symbol")
    if name.startswith(
        (
            "find_distance_with_location_name",
            "find_address_with_lat_lon",
            "find_phone_number_with_location_name",
            "find_temperature",
            "find_temperature_f_with_location",
            "convert_currency",
            "convert_currency_canonicalize",
        )
    ):
        opportunities.append("derived_value:extract_service_answer_field")
    if name.startswith(DIRECT_SERVICE_HELPER_PREFIXES):
        opportunities.append("state_precondition:next_service_tool_call")
    if name.startswith(DOWNSTREAM_SERVICE_HELPER_PREFIXES):
        opportunities.append("state_precondition:recover_from_tool_error")
    if (
        name.startswith("add_reminder_content_and_")
        and "_time" in name
        and not (
            name.startswith("add_reminder_content_and_week_delta_and_time")
            and "_location" not in name
        )
    ):
        opportunities.append("composite:prepare_reminder_creation_args")
    return opportunities


def cohort_policy_report(
    scenario_names: Iterable[str],
    *,
    categories_by_name: dict[str, Iterable[str]] | None = None,
    generation_enabled: bool,
    registry_tool_count: int = 0,
) -> dict[str, Any]:
    """Summarize whether a run is likely to exercise retained-tool evolution."""

    names = list(scenario_names)
    categories_by_name = categories_by_name or {}
    family_counts = Counter(base_task_family(name) for name in names)
    strata_counts: Counter[str] = Counter()
    helper_fit_counts: Counter[str] = Counter()
    birth_opportunity_counts: Counter[str] = Counter()
    contaminated: list[str] = []
    insufficient: list[str] = []
    per_scenario: list[dict[str, Any]] = []

    for name in names:
        categories = tuple(categories_by_name.get(name, ()))
        helper_fit = expected_helper_fit(name, categories)
        birth_opportunities = expected_birth_opportunities(name, categories)
        strata_counts.update(classify_task_strata(name, categories))
        helper_fit_counts.update(helper_fit or ["no_current_helper_fit"])
        birth_opportunity_counts.update(
            birth_opportunities or ["no_current_birth_opportunity"]
        )
        lower_name = name.lower()
        if any(token in lower_name for token in EXTERNAL_SERVICE_TOKENS):
            contaminated.append(name)
        if "insufficient_information" in lower_name or "INSUFFICIENT_INFORMATION" in {
            category.upper() for category in categories
        }:
            insufficient.append(name)
        per_scenario.append(
            {
                "scenario": name,
                "base_task_family": base_task_family(name),
                "expected_helper_fit": helper_fit,
                "expected_birth_opportunities": birth_opportunities,
            }
        )

    scenario_count = len(names)
    largest_family = max(family_counts.values(), default=0)
    largest_family_share = largest_family / scenario_count if scenario_count else 0.0
    if scenario_count >= 60:
        required_families = 8
    elif scenario_count >= 30:
        required_families = 6
    elif scenario_count >= 20:
        required_families = 5
    else:
        required_families = min(scenario_count, 4)
    if scenario_count >= 500:
        max_family_share = 0.08
        max_family_variants = max(8, int(scenario_count * 0.05))
    elif scenario_count >= 60:
        max_family_share = 0.20
        max_family_variants = 8
    elif scenario_count >= 30:
        max_family_share = 0.20
        max_family_variants = 4
    elif scenario_count >= 20:
        max_family_share = 0.25
        max_family_variants = 2
    else:
        max_family_share = 1.00
        max_family_variants = scenario_count

    has_birth_path = any(
        key != "no_current_birth_opportunity" and count > 0
        for key, count in birth_opportunity_counts.items()
    )
    has_helper_fit = any(
        key != "no_current_helper_fit" and count > 0
        for key, count in helper_fit_counts.items()
    )
    no_helper_fit_count = helper_fit_counts.get("no_current_helper_fit", 0)
    helper_fit_scenario_count = scenario_count - no_helper_fit_count
    helper_fit_share = (
        helper_fit_scenario_count / scenario_count if scenario_count else 0.0
    )
    no_helper_fit_share = (
        no_helper_fit_count / scenario_count if scenario_count else 0.0
    )
    helper_lane_counts = {
        key: count
        for key, count in helper_fit_counts.items()
        if key != "no_current_helper_fit"
    }
    largest_helper_lane = max(helper_lane_counts.values(), default=0)
    largest_helper_lane_share = (
        largest_helper_lane / scenario_count if scenario_count else 0.0
    )
    post_birth_reuse: dict[str, dict[str, Any]] = {}
    for index, row in enumerate(per_scenario):
        for opportunity in row["expected_birth_opportunities"]:
            if not isinstance(opportunity, str):
                continue
            helper_names = OPPORTUNITY_HELPERS.get(opportunity, ())
            if not helper_names:
                continue
            current = post_birth_reuse.setdefault(
                opportunity,
                {
                    "helper_names": list(helper_names),
                    "first_birth_index": index,
                    "first_birth_scenario": row["scenario"],
                    "later_fit_count": 0,
                    "later_distinct_base_families": 0,
                    "later_fit_scenarios": [],
                },
            )
            if index < current["first_birth_index"]:
                current["first_birth_index"] = index
                current["first_birth_scenario"] = row["scenario"]

    for opportunity, summary in post_birth_reuse.items():
        helpers = set(summary["helper_names"])
        first_index = int(summary["first_birth_index"])
        later_scenarios: list[str] = []
        later_families: set[str] = set()
        for row in per_scenario[first_index + 1 :]:
            helper_fit_set = set(row["expected_helper_fit"])
            if helpers & helper_fit_set:
                later_scenarios.append(str(row["scenario"]))
                later_families.add(str(row["base_task_family"]))
        summary["later_fit_count"] = len(later_scenarios)
        summary["later_distinct_base_families"] = len(later_families)
        summary["later_fit_scenarios"] = later_scenarios[:20]

    has_post_birth_reuse_opportunity = any(
        int(summary["later_fit_count"]) > 0 for summary in post_birth_reuse.values()
    )
    warnings = [
        warning
        for warning in (
            "external_service_cases_present" if contaminated else "",
            "too_few_base_families" if len(family_counts) < required_families else "",
            "family_share_above_limit"
            if scenario_count >= 20 and largest_family_share > max_family_share
            else "",
            "near_duplicate_family_variants_above_limit"
            if scenario_count >= 20 and largest_family > max_family_variants
            else "",
            "weak_negative_no_helper_coverage"
            if scenario_count >= 20
            and registry_tool_count > 0
            and no_helper_fit_share < 0.2
            else "",
            "known_helper_lane_overrepresented"
            if scenario_count >= 20 and largest_helper_lane_share > 0.6
            else "",
            "no_expected_helper_fit" if not has_helper_fit else "",
            "low_expected_helper_fit_share"
            if scenario_count >= 12 and helper_fit_share < 0.5
            else "",
            "generation_enabled_but_no_expected_birth_path"
            if generation_enabled and not has_birth_path
            else "",
            "generation_enabled_but_no_post_birth_reuse_opportunity"
            if generation_enabled
            and has_birth_path
            and not has_post_birth_reuse_opportunity
            else "",
        )
        if warning
    ]
    quality_failures = [
        failure
        for failure in (
            "too_few_base_families"
            if scenario_count >= 20 and len(family_counts) < required_families
            else "",
            "family_share_above_limit"
            if scenario_count >= 20 and largest_family_share > max_family_share
            else "",
            "near_duplicate_family_variants_above_limit"
            if scenario_count >= 20 and largest_family > max_family_variants
            else "",
            "weak_negative_no_helper_coverage"
            if scenario_count >= 20
            and registry_tool_count > 0
            and no_helper_fit_share < 0.2
            else "",
            "known_helper_lane_overrepresented"
            if scenario_count >= 20 and largest_helper_lane_share > 0.6
            else "",
        )
        if failure
    ]
    should_block_birth = (
        generation_enabled
        and registry_tool_count == 0
        and not has_birth_path
        and not has_helper_fit
    )
    should_block_quality = bool(quality_failures)
    return {
        "scenario_count": scenario_count,
        "distinct_base_task_families": len(family_counts),
        "required_distinct_base_task_families": required_families,
        "largest_family_share": largest_family_share,
        "max_allowed_family_share": max_family_share,
        "largest_family_variant_count": largest_family,
        "max_allowed_family_variants": max_family_variants,
        "family_counts": dict(family_counts.most_common()),
        "strata_counts": dict(strata_counts.most_common()),
        "expected_helper_fit_counts": dict(helper_fit_counts.most_common()),
        "expected_helper_fit_share": helper_fit_share,
        "no_current_helper_fit_share": no_helper_fit_share,
        "largest_helper_lane_share": largest_helper_lane_share,
        "expected_birth_opportunity_counts": dict(
            birth_opportunity_counts.most_common()
        ),
        "contaminated_external_service_scenarios": contaminated,
        "insufficient_information_scenarios": insufficient,
        "generation_enabled": generation_enabled,
        "registry_tool_count": registry_tool_count,
        "has_expected_birth_path": has_birth_path,
        "has_expected_helper_fit": has_helper_fit,
        "has_post_birth_reuse_opportunity": has_post_birth_reuse_opportunity,
        "post_birth_reuse_opportunities": post_birth_reuse,
        "should_block": should_block_birth,
        "should_block_birth": should_block_birth,
        "should_block_quality": should_block_quality,
        "quality_gate_status": "fail" if should_block_quality else "pass",
        "quality_gate_failures": quality_failures,
        "decision_use": (
            "suitable_for_broad_value_decision"
            if scenario_count >= 20
            and len(family_counts) >= required_families
            and largest_family_share <= max_family_share
            and not should_block_quality
            else "suitable_for_early_value_only"
        ),
        "warnings": warnings,
    }
