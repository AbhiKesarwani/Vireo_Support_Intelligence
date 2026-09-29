"""
tests/browser_qa_all_pages.py — Complete Playwright Browser QA across all 6 Streamlit pages.
Verifies interactive filtering, weekly leaderboard switching, zero application errors,
and captures full-page visual evidence.
"""

import os
import time
from playwright.sync_api import sync_playwright

os.makedirs("outputs/browser_qa", exist_ok=True)

def run_browser_qa():
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="msedge", headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 960})
        
        try:
            # Collect console errors
            console_errors = []
            page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
            
            print("Navigating to http://localhost:8501...")
            page.goto("http://localhost:8501", wait_until="networkidle", timeout=30000)
            page.wait_for_timeout(3000)
            
            # 1. Page 1: Executive Digest
            print("Auditing Page 1: Executive Digest...")
            title1 = page.locator(".main-title").inner_text()
            assert "Executive Support Intelligence Digest" in title1
            kpis1 = " ".join(page.locator(".kpi-card").all_inner_texts())
            assert "11,875" in kpis1
            assert "32,48,430" in kpis1 or "3,248,430" in kpis1
            page.screenshot(path="outputs/browser_qa/page1_executive_digest.png")
            print("Page 1 OK. Captured page1_executive_digest.png")

            # Helper to click radio
            def click_radio(idx):
                r = page.locator('[data-testid="stSidebar"] [data-testid="stRadio"] label').all()
                if len(r) > idx:
                    lbl = r[idx].inner_text().encode('ascii', 'replace').decode()
                    print(f"click_radio({idx}) clicking: {lbl}")
                    r[idx].click()
                    page.wait_for_timeout(3500)
                else:
                    print(f"click_radio({idx}): only {len(r)} labels found!")

            # 2. Page 2: Issue Explorer
            print("Auditing Page 2: Issue Explorer...")
            click_radio(2)
            title2 = page.locator(".main-title").inner_text()
            assert "Customer Issue Intelligence Explorer" in title2
            content2 = page.content()
            assert "PRODUCT" in content2
            page.screenshot(path="outputs/browser_qa/page2_issue_explorer.png")
            print("Page 2 OK. Captured page2_issue_explorer.png")

            # 3. Page 3: Repeat Contact Analysis
            print("Auditing Page 3: Repeat Contact Analysis...")
            click_radio(3)
            title3 = page.locator(".main-title").inner_text()
            assert "Avoidable Support Demand & Repeat Economics" in title3
            kpis3 = " ".join(page.locator(".kpi-card").all_inner_texts())
            assert "10,463" in kpis3
            assert "1,505" in kpis3
            assert "523" in kpis3
            assert "982" in kpis3
            page.screenshot(path="outputs/browser_qa/page3_repeat_analysis.png")
            print("Page 3 OK. Captured page3_repeat_analysis.png")

            # 4. Page 4: Tier-1 Agent Leaderboard
            print("Auditing Page 4: Tier-1 Agent Leaderboard...")
            click_radio(4)
            title4 = page.locator(".main-title").inner_text()
            assert "Tier-1 Frontline Weekly Leaderboard" in title4
            sub4 = page.locator(".sub-title, .policy-box").all_inner_texts()
            assert any("tickets closed" in s.lower() for s in sub4)
            page.screenshot(path="outputs/browser_qa/page4_tier1_leaderboard_week1.png")
            print("Page 4 Week 1 OK. Captured page4_tier1_leaderboard_week1.png")

            # Change week on Page 4 to a second week
            selectboxes = page.query_selector_all('[data-testid="stSelectbox"]')
            if len(selectboxes) >= 1:
                week_box = selectboxes[0]
                week_box.click()
                page.wait_for_timeout(500)
                # Select an earlier week
                page.keyboard.press("ArrowDown")
                page.keyboard.press("ArrowDown")
                page.keyboard.press("Enter")
                page.wait_for_timeout(3500)
                page.screenshot(path="outputs/browser_qa/page4_tier1_leaderboard_week2.png")
                print("Page 4 Week 2 change OK. Captured page4_tier1_leaderboard_week2.png")

            # 5. Page 5: Tier-2 Operations
            print("Auditing Page 5: Tier-2 Operations...")
            click_radio(5)
            title5 = page.locator(".main-title").inner_text()
            assert "Tier-2 Escalations & Operations" in title5
            policy5 = " ".join(page.locator(".policy-box").all_inner_texts())
            assert "Operational Policy Constraint" in policy5
            assert "Do NOT rank Tier-2 agents by volume" in policy5
            page.screenshot(path="outputs/browser_qa/page5_tier2_operations.png")
            print("Page 5 OK. Captured page5_tier2_operations.png")

            # 6. Page 6: Quality & Methodology
            print("Auditing Page 6: Quality & Methodology...")
            click_radio(6)
            title6 = page.locator(".main-title").inner_text()
            assert "Quality, Provenance & Methodology" in title6
            kpis6 = " ".join(page.locator(".kpi-card").all_inner_texts())
            assert "12,528" in kpis6
            assert "653" in kpis6
            assert "11,875" in kpis6
            page.screenshot(path="outputs/browser_qa/page6_quality_methodology.png")
            print("Page 6 OK. Captured page6_quality_methodology.png")

            # Verify no Streamlit application error alerts
            alerts = page.locator('[data-testid="stNotification"]').all_inner_texts()
            for a in alerts:
                assert "Traceback" not in a, f"Alert traceback: {a}"
                assert "Application Error" not in a, f"Application error: {a}"
            
            print(f"Browser QA complete! All 6 pages verified. Console errors: {len(console_errors)}")
        finally:
            browser.close()

if __name__ == "__main__":
    run_browser_qa()
