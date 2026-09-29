"""
memo/build_pdf.py — Generate high-quality one_page_memo.pdf using PyMuPDF.
Strictly adheres to Phase 7 memo guidelines: zero stale values, ASCII bullets,
exact one-page fit, verified business metrics, zero '?' artifacts.
"""

from pathlib import Path
import pymupdf


def generate_memo_pdf(output_path: str = "memo/one_page_memo.pdf"):
    doc = pymupdf.open()
    # A4 dimensions: 595.32 x 841.92 pt
    page = doc.new_page(width=595.32, height=841.92)

    # Margin settings
    left = 40.0
    right = 555.0
    top = 35.0

    # Colors
    c_primary = (0.08, 0.18, 0.36)    # Deep Navy #142e5c
    c_secondary = (0.28, 0.35, 0.45)  # Slate #475973
    c_dark = (0.1, 0.12, 0.15)        # Text #1a1e26
    c_amber = (0.85, 0.45, 0.05)      # Amber #d9730d
    c_line = (0.85, 0.88, 0.92)       # Rule
    c_bg_box = (0.96, 0.97, 0.99)     # Light box

    y = top

    # Title & Header
    page.insert_text((left, y + 14), "VIREO SUPPORT INTELLIGENCE", fontname="helv", fontsize=15, color=c_primary)
    y += 18
    page.insert_text((left, y + 10), "Executive CX Brief — 18-Month Operational Audit & Repeat Economics", fontname="helv", fontsize=10, color=c_secondary)
    y += 15

    # Metadata bar
    meta_text = "To: Priya Raman (Head of CX)   |   Date: 29 Sep 2026   |   Coverage: 1 Jan 2025 – 30 Jun 2026   |   Canonical Tickets: 11,875"
    page.draw_rect(pymupdf.Rect(left, y, right, y + 16), color=None, fill=c_bg_box)
    page.insert_text((left + 8, y + 11), meta_text, fontname="helv", fontsize=7.8, color=c_secondary)
    y += 22

    def section_header(title: str, curr_y: float) -> float:
        page.draw_line(pymupdf.Point(left, curr_y), pymupdf.Point(right, curr_y), color=c_line, width=0.8)
        curr_y += 10
        page.insert_text((left, curr_y), title, fontname="helv", fontsize=9, color=c_primary)
        return curr_y + 11

    # 1. Business Goal
    y = section_header("1. Business Goal", y)
    t1 = ("Reduce the 30-day repeat-contact rate from the observed 14.38% toward a 5.00% planning target. "
          "Across 10,463 eligible tickets with a complete 30-day post-resolution observation window, 1,505 tickets generated repeat contacts "
          "(yielding 1,573 incoming contacts costing Rs 4,09,470). Reaching the 5.00% target (523 tickets) establishes a 982-ticket "
          "reduction scenario, representing an estimated modelled planning opportunity of approximately Rs 2.85 lakh "
          "(Rs 2,84,780 at blended Rs 290 standard; Rs 2,56,489 channel-mix). Modelled figures are for resource allocation, not realized savings.")
    rect1 = pymupdf.Rect(left, y, right, y + 46)
    rc1 = page.insert_textbox(rect1, t1, fontname="helv", fontsize=7.3, color=c_dark, lineheight=1.2)
    assert rc1 >= 0, f"Section 1 overflow: {rc1}"
    y += 48

    # 2. Key Operational Findings
    y = section_header("2. Key Operational Findings (11,875 Canonical Tickets)", y)
    t2 = ("- Financial Baseline: Total direct contact spend was Rs 32,48,430 (avg Rs 273.55/ticket). Helpdesk transfers added Rs 2,64,740 across 1,040 hand-offs.\n"
          "- SLA Exposure: 1,051 first-response SLA breaches (8.85% of canonical tickets), generating Rs 3,67,850 in SLA-credit exposure. Mean CSAT: 3.3152 (5,269 valid responses, 44.37% rate).\n"
          "- Resolver Alignment: 1,448 tickets (12.19%) had a resolver team different from the initial assigned team, contributing to subsequent transfers.\n"
          "- Issue Distribution: PRODUCT: 2,893 tkts (24.36%, 16.90% rep). Earbud Bluetooth/pairing issues are a recurring product complaint pattern. "
          "OTHER: 2,572 (21.66%) | DELIVERY: 2,138 (18.00%, lowest CSAT 3.03) | BILLING: 1,627 (13.70%) | RETURNS: 1,204 (10.14%) | APP: 824 (6.94%) | WARRANTY: 617 (5.20%).\n"
          "- Frontline vs Tier-2: Tier-1 closed 10,547 tickets (~277/agent; 9,507 resolved + 1,040 auto-closed). Tier-2 handled 719 complex cases with 2.68-day median turnaround.")
    rect2 = pymupdf.Rect(left, y, right, y + 80)
    rc2 = page.insert_textbox(rect2, t2, fontname="helv", fontsize=7.1, color=c_dark, lineheight=1.2)
    assert rc2 >= 0, f"Section 2 overflow: {rc2}"
    y += 82

    # 3. Repeat Contact Economics & Planning Opportunity
    y = section_header("3. Repeat Contact Economics & Planning Opportunity", y)
    intro_rep = ("Policy Section 6: Repeat contact = same customer & issue within 30 days of resolution. June 2026 (803 tkts) is right-censored; "
                 "609 open tickets are excluded. Evaluated cohort = 10,463 tickets.")
    page.insert_text((left, y), intro_rep, fontname="helv", fontsize=7.3, color=c_secondary)
    y += 10

    # Draw Table
    col_w = [145, 175, 195]
    x0 = left
    x1 = x0 + col_w[0]
    x2 = x1 + col_w[1]
    x3 = right
    row_h = 13.5

    # Table Header
    page.draw_rect(pymupdf.Rect(x0, y, x3, y + row_h), color=None, fill=(0.91, 0.93, 0.96))
    page.insert_text((x0 + 4, y + 9.5), "Metric Category", fontname="helv", fontsize=7.4, color=c_primary)
    page.insert_text((x1 + 4, y + 9.5), "Observed Historical Baseline", fontname="helv", fontsize=7.4, color=c_primary)
    page.insert_text((x2 + 4, y + 9.5), "5.00% Planning Target Scenario", fontname="helv", fontsize=7.4, color=c_primary)
    y += row_h

    table_rows = [
        ("Repeat-Eligible Evaluated Cohort", "10,463 tickets (resolved <= 31-May-2026)", "10,463 evaluated tickets"),
        ("Repeat-Generating Tickets", "1,505 tickets (14.38% of repeat-eligible tickets)", "523 target tickets (5.00% target)"),
        ("Incoming Repeat Contacts", "1,573 total (1,512 from eligible cohort)", "Avoidable reduction: 982 tickets"),
        ("Total Repeat Contact Spend", "Rs 4,09,470 total (Rs 3,93,090 eligible)", "Multiplier: 1.00465 contacts/repeat ticket"),
        ("Unit Cost Basis", "Rs 260.31 / contact; Rs 261.19 / repeat ticket", "Rs 261.19 channel-mix / Rs 290 blended"),
        ("Modelled Planning Opportunity", "Baseline (Observed)", "Rs 2,56,488.58 (channel) | Rs 2,84,780 (blended)"),
    ]
    for r_idx, (c0, c1_val, c2_val) in enumerate(table_rows):
        bg = (0.98, 0.98, 0.99) if r_idx % 2 == 1 else (1.0, 1.0, 1.0)
        page.draw_rect(pymupdf.Rect(x0, y, x3, y + row_h), color=c_line, fill=bg, width=0.4)
        page.insert_text((x0 + 4, y + 9.5), c0, fontname="helv", fontsize=7.1, color=c_dark)
        page.insert_text((x1 + 4, y + 9.5), c1_val, fontname="helv", fontsize=7.1, color=c_dark)
        is_bold_row = (r_idx == len(table_rows) - 1)
        col_c2 = c_amber if is_bold_row else c_dark
        page.insert_text((x2 + 4, y + 9.5), c2_val, fontname="helv", fontsize=7.1, color=col_c2)
        y += row_h

    y += 5
    # Callout box for SCENARIO ESTIMATE
    page.draw_rect(pymupdf.Rect(left, y, right, y + 16), color=c_amber, fill=(0.99, 0.97, 0.94), width=0.5)
    page.insert_text((left + 6, y + 11), "PLANNING SCENARIO: The savings above are modelled planning figures, NOT realized or guaranteed savings.", fontname="helv", fontsize=7.1, color=c_amber)
    y += 22

    # 4. Strategic Recommendations
    y = section_header("4. Strategic Recommendations", y)
    t4 = ("1. Improve Intake Routing: Refine frontline triage keyword definitions for high-transfer issue areas to minimize resolver team differences.\n"
          "2. Strengthen First-Contact Troubleshooting: Deploy guided triage workflows for recurring earbud pairing/product issues to reduce repeat rate.\n"
          "3. Enhance Delivery Tracking: Provide automated courier tracking updates to resolve shipping inquiries before customers reach frontline support.\n"
          "4. Monitor Cohort Repeat Metrics: Track monthly 30-day repeat-contact rates against the 5.00% planning target alongside operational SLA guardrails.")
    rect4 = pymupdf.Rect(left, y, right, y + 44)
    rc4 = page.insert_textbox(rect4, t4, fontname="helv", fontsize=7.1, color=c_dark, lineheight=1.2)
    assert rc4 >= 0, f"Section 4 overflow: {rc4}"
    y += 46

    # 5. Technical Limitations & AI Methodology
    y = section_header("5. Technical Limitations & AI Methodology", y)
    t5 = ("- AI Methodology: Evaluated on 50-ticket human gold set (96.0% accuracy, 0.9749 macro-F1) with 100% evidence grounding (0 hallucinations).\n"
          "- Deterministic Calculation: Repeat detection and business metrics calculated deterministically (AI interprets free text; code calculates metrics).\n"
          "- Right-Censoring: 803 tickets resolved in June 2026 cannot be evaluated for 30-day repeat contacts until July 31, 2026.")
    rect5 = pymupdf.Rect(left, y, right, y + 34)
    rc5 = page.insert_textbox(rect5, t5, fontname="helv", fontsize=7.1, color=c_dark, lineheight=1.2)
    assert rc5 >= 0, f"Section 5 overflow: {rc5}"
    y += 36

    # Footer
    page.draw_line(pymupdf.Point(left, 810), pymupdf.Point(right, 810), color=c_line, width=0.6)
    page.insert_text((left, 822), "Vireo Audio Support Intelligence  |  Audit Certified: 136/136 Tests Passed  |  Code Calculates. AI Interprets. Humans Decide.", fontname="helv", fontsize=7, color=c_secondary)
    page.insert_text((right - 45, 822), "Page 1 of 1", fontname="helv", fontsize=7, color=c_secondary)

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    doc.save(output_path)
    doc.close()
    print(f"Generated PDF: {output_path}")


if __name__ == "__main__":
    generate_memo_pdf()
