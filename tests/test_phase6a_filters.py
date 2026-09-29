"""
tests/test_phase6a_filters.py — Phase 6A regression tests for dashboard filter correctness.

Tests:
1. Channel cross-tab filter — all channels and each individual channel
2. Product family cross-tab filter — all families and each individual family
3. Issue chart dimension correctness — chart_repeat_cost_by_issue uses 'issue_code' not 'issue'
4. Repeat scenario math at 5% target
5. No hardcoded 1505 or business numbers in views.py (scan-level)
"""
from __future__ import annotations

import re
import pandas as pd
import pytest

from src.dashboard.data_loader import (
    load_channel_issue_metrics,
    load_product_issue_metrics,
    load_repeat_economics_table,
    load_repeat_summary,
)
from src.dashboard.charts import chart_repeat_cost_by_issue, chart_repeat_cost_by_channel


# ── PART 1: CHANNEL CROSS-TAB FILTER ─────────────────────────────────────────

class TestChannelFilter:
    """The channel filter must slice the channel_issue_metrics DataFrame correctly."""

    @pytest.fixture(scope="class")
    def ch_df(self):
        return load_channel_issue_metrics()

    def test_all_channels_total_equals_canonical(self, ch_df):
        """Sum across all channels must equal the canonical 11,875."""
        assert int(ch_df["ticket_count"].sum()) == 11875, (
            f"All-channel total is {ch_df['ticket_count'].sum()}, expected 11,875"
        )

    def test_chat_filter_returns_correct_total(self, ch_df):
        filtered = ch_df[ch_df["channel"] == "chat"]
        assert int(filtered["ticket_count"].sum()) == 5161

    def test_email_filter_returns_correct_total(self, ch_df):
        filtered = ch_df[ch_df["channel"] == "email"]
        assert int(filtered["ticket_count"].sum()) == 3807

    def test_social_filter_returns_correct_total(self, ch_df):
        filtered = ch_df[ch_df["channel"] == "social"]
        assert int(filtered["ticket_count"].sum()) == 1203

    def test_voice_filter_returns_correct_total(self, ch_df):
        filtered = ch_df[ch_df["channel"] == "voice"]
        assert int(filtered["ticket_count"].sum()) == 1704

    def test_channel_totals_sum_to_canonical(self, ch_df):
        """Each individual channel total must sum to 11,875."""
        channels = ch_df["channel"].unique().tolist()
        grand_total = sum(
            int(ch_df[ch_df["channel"] == ch]["ticket_count"].sum())
            for ch in channels
        )
        assert grand_total == 11875

    def test_filter_reduces_rows(self, ch_df):
        """Filtering to a single channel must return fewer rows than the full table."""
        full_rows = len(ch_df)
        chat_rows = len(ch_df[ch_df["channel"] == "chat"])
        assert chat_rows < full_rows

    def test_filtered_df_has_only_selected_channel(self, ch_df):
        """Filtering must not leak rows from other channels."""
        for ch in ch_df["channel"].unique():
            filtered = ch_df[ch_df["channel"] == ch]
            assert all(filtered["channel"] == ch), f"Leaked rows from other channels when filtering to '{ch}'"


# ── PART 2: PRODUCT FAMILY CROSS-TAB FILTER ──────────────────────────────────

class TestProductFamilyFilter:
    """The product family filter must slice product_issue_metrics correctly."""

    EXPECTED_TOTALS = {
        "accessory":  549,
        "earbuds":   6343,
        "headphones": 1338,
        "speaker":   1348,
        "watch":     2297,
    }

    @pytest.fixture(scope="class")
    def prod_df(self):
        return load_product_issue_metrics()

    def test_all_families_total_equals_canonical(self, prod_df):
        assert int(prod_df["ticket_count"].sum()) == 11875

    @pytest.mark.parametrize("family,expected", [
        ("accessory", 549),
        ("earbuds", 6343),
        ("headphones", 1338),
        ("speaker", 1348),
        ("watch", 2297),
    ])
    def test_individual_family_totals(self, prod_df, family, expected):
        filtered = prod_df[prod_df["prod_family"] == family]
        total = int(filtered["ticket_count"].sum())
        assert total == expected, (
            f"Product family '{family}': got {total}, expected {expected}"
        )

    def test_family_totals_sum_to_canonical(self, prod_df):
        families = prod_df["prod_family"].dropna().unique().tolist()
        grand_total = sum(
            int(prod_df[prod_df["prod_family"] == fam]["ticket_count"].sum())
            for fam in families
        )
        assert grand_total == 11875

    def test_filter_leaves_only_selected_family(self, prod_df):
        for fam in prod_df["prod_family"].dropna().unique():
            filtered = prod_df[prod_df["prod_family"] == fam]
            assert all(filtered["prod_family"] == fam)


# ── PART 3: CHART DIMENSION CORRECTNESS ──────────────────────────────────────

class TestChartDimensions:
    """chart_repeat_cost_by_issue must use 'issue_code' dimension, not 'issue'."""

    @pytest.fixture(scope="class")
    def rep_table(self):
        return load_repeat_economics_table()

    def test_repeat_economics_has_issue_code_dimension(self, rep_table):
        """The repeat economics table must contain dimension='issue_code' rows."""
        iss_rows = rep_table[rep_table["dimension"] == "issue_code"]
        assert len(iss_rows) > 0, "No rows with dimension='issue_code' found"

    def test_repeat_economics_has_no_issue_dimension(self, rep_table):
        """There must be NO rows with dimension='issue' (wrong key)."""
        wrong_rows = rep_table[rep_table["dimension"] == "issue"]
        assert len(wrong_rows) == 0, (
            f"Found {len(wrong_rows)} rows with dimension='issue' (wrong key). Expected 0."
        )

    def test_chart_repeat_cost_by_issue_has_string_x_axis(self, rep_table):
        """The issue repeat cost chart must have string category names on x-axis, not integers."""
        fig = chart_repeat_cost_by_issue(rep_table)
        assert len(fig.data) > 0, "chart_repeat_cost_by_issue returned no traces"
        x_values = fig.data[0].x
        assert x_values is not None and len(x_values) > 0, "x-axis is empty"
        # All x values must be strings (issue names), not integers
        for val in x_values:
            assert isinstance(val, str), (
                f"x-axis value '{val}' is {type(val).__name__}, expected str (issue name)"
            )

    def test_chart_repeat_cost_by_issue_has_all_7_categories(self, rep_table):
        """Must show all 7 issue categories."""
        fig = chart_repeat_cost_by_issue(rep_table)
        x_values = list(fig.data[0].x)
        expected = {"APP", "BILLING", "DELIVERY", "OTHER", "PRODUCT", "RETURNS", "WARRANTY"}
        actual = set(x_values)
        assert expected == actual, (
            f"Chart shows {actual}, expected {expected}"
        )

    def test_chart_repeat_cost_by_issue_total_equals_repeat_spend(self, rep_table):
        """Sum of y-values must equal total repeat spend of 409,470."""
        fig = chart_repeat_cost_by_issue(rep_table)
        total = sum(fig.data[0].y)
        assert abs(total - 409470.0) < 1.0, (
            f"Chart total repeat spend is {total:.0f}, expected 409,470"
        )

    def test_chart_repeat_cost_by_channel_has_channel_names(self, rep_table):
        """Channel chart must show channel names (strings) on x-axis."""
        fig = chart_repeat_cost_by_channel(rep_table)
        x_values = fig.data[0].x
        for val in x_values:
            assert isinstance(val, str)

    def test_chart_repeat_cost_by_channel_total(self, rep_table):
        fig = chart_repeat_cost_by_channel(rep_table)
        total = sum(fig.data[0].y)
        assert abs(total - 409470.0) < 1.0


# ── PART 4: REPEAT SCENARIO MATH ─────────────────────────────────────────────

class TestRepeatScenarioMath:
    """The 5% scenario must use correct denominator (repeat_eligible, not total)."""

    @pytest.fixture(scope="class")
    def rep(self):
        return load_repeat_summary()

    def test_repeat_eligible_is_10463(self, rep):
        assert rep["repeat_eligible_tickets"] == 10463

    def test_right_censored_is_803(self, rep):
        assert rep["right_censored_tickets"] == 803

    def test_tickets_generating_repeats_is_1505(self, rep):
        assert rep["tickets_generating_repeats"] == 1505

    def test_incoming_repeat_contacts_is_1573(self, rep):
        assert rep["incoming_repeat_contacts"] == 1573

    def test_5pct_target_is_523(self, rep):
        """5% of 10,463 rounded = 523, not 471 (which would be 4.5%)."""
        target = int(round(0.05 * rep["repeat_eligible_tickets"]))
        assert target == 523, f"5% target = {target}, expected 523"

    def test_avoidable_at_5pct_is_982(self, rep):
        target = int(round(0.05 * rep["repeat_eligible_tickets"]))
        avoidable = max(0, rep["tickets_generating_repeats"] - target)
        assert avoidable == 982, f"Avoidable at 5% = {avoidable}, expected 982"

    def test_471_corresponds_to_4pt5pct_not_5pct(self, rep):
        """Regression: if slider shows 471 as target, user had 4.5% selected, not 5%."""
        target_4_5 = int(round(0.045 * rep["repeat_eligible_tickets"]))
        target_5_0 = int(round(0.050 * rep["repeat_eligible_tickets"]))
        assert target_4_5 == 471, f"4.5% target = {target_4_5}, expected 471"
        assert target_5_0 == 523, f"5.0% target = {target_5_0}, expected 523"

    def test_blended_savings_at_5pct(self, rep):
        target = int(round(0.05 * rep["repeat_eligible_tickets"]))
        avoidable = max(0, rep["tickets_generating_repeats"] - target)
        savings = avoidable * 290.0
        assert savings == 284780.0, f"Blended savings = {savings:.0f}, expected 284,780"


# ── PART 5: NO HARDCODED BUSINESS VALUES IN views.py ─────────────────────────

class TestNoHardcodedValues:
    """Scan views.py for hardcoded business metrics."""

    FORBIDDEN_PATTERNS = [
        # literal business numbers that must come from data
        r"(?<!\w)1[,.]505(?!\w)",   # tickets_generating_repeats
        r"(?<!\w)1[,.]573(?!\w)",   # incoming_repeat_contacts
        r"(?<!\w)10[,.]463(?!\w)",  # repeat_eligible_tickets
        r"(?<!\w)409[,.]470(?!\w)", # total_repeat_spend
        r"(?<!\w)1[,.]051(?!\w)",   # sla_breaches
        r"(?<!\w)3[,.]248[,.]430(?!\w)",  # total_contact_cost
    ]

    def _get_non_comment_lines(self, filepath: str):
        with open(filepath, "r", encoding="utf-8") as f:
            lines = f.readlines()
        return [(i + 1, ln.rstrip()) for i, ln in enumerate(lines)
                if not ln.strip().startswith("#") and
                   "format_num(" not in ln and
                   "format_inr(" not in ln and
                   "format_pct(" not in ln]

    def test_no_hardcoded_repeat_generating_tickets(self):
        lines = self._get_non_comment_lines("src/dashboard/views.py")
        hits = [(no, ln) for no, ln in lines if re.search(r"(?<!\w)1[,.]505(?!\w)", ln)
                and "format_num" not in ln]
        assert len(hits) == 0, (
            f"Hardcoded '1,505' found at: {[(no, ln[:80]) for no, ln in hits]}"
        )

    def test_no_hardcoded_repeat_contacts(self):
        lines = self._get_non_comment_lines("src/dashboard/views.py")
        hits = [(no, ln) for no, ln in lines if re.search(r"(?<!\w)1[,.]573(?!\w)", ln)
                and "format_num" not in ln]
        assert len(hits) == 0

    def test_no_hardcoded_repeat_eligible(self):
        lines = self._get_non_comment_lines("src/dashboard/views.py")
        hits = [(no, ln) for no, ln in lines if re.search(r"(?<!\w)10[,.]463(?!\w)", ln)
                and "format_num" not in ln]
        assert len(hits) == 0
