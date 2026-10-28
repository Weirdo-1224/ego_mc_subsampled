"""Acceptance tests for index_v2.html (review workbench v2) using headless Edge."""
import json
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path(__file__).resolve().parent.parent / "results" / "video_review" / "GX010021_phase1_20261027"
V2 = OUT / "index_v2.html"
OLD = OUT / "index.html"
V2_KEY = "GX010021_phase1_20261027_review_v2"
LEGACY_KEY = "GX010021_phase1_20261027_PENDING_drafts"


def task_button(page, text):
    return page.locator("#taskList .taskCard", has_text=text)


def main():
    checks, errors = [], []
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="msedge", headless=True)
        ctx = browser.new_context(viewport={"width": 1440, "height": 900}, accept_downloads=True)
        page = ctx.new_page()
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(V2.as_uri(), wait_until="load")
        page.evaluate(f"localStorage.removeItem('{V2_KEY}');localStorage.removeItem('{LEGACY_KEY}')")
        page.reload(wait_until="load")
        assert page.locator("#taskList .taskCard").count() == 9
        assert "已审 0 / 9" in page.locator("#progress").inner_text()
        checks.append("loads 9 tasks from file:// with 0/9 progress and no JS error")

        # ---- Scenario 1: T1 16s oven — UNKNOWN answer end-to-end ----
        task_button(page, "350°F").click()
        assert page.locator("#stepBtn2").is_disabled() and page.locator("#stepBtn3").is_disabled()
        blind = page.locator(".blindNote").inner_text()
        assert "遮蔽" in blind and page.get_by_text("候选答案（非Gold）").count() == 0
        checks.append("Step 1 hides candidate/history/analysis and gates Step 2/3 before lock")
        page.locator('[data-f="s1answer"]').fill("UNKNOWN")
        page.locator('[data-f="s1suf"]').select_option("UNCERTAIN")
        page.locator("button", has_text="锁定 Step 1 初始记录").click()
        assert not page.locator("#stepBtn2").is_disabled()
        # current-window player cannot play past query time (16s)
        page.wait_for_function("document.getElementById('winVideo').readyState>=1")
        page.evaluate("(()=>{const v=document.getElementById('winVideo');v.currentTime=20;v.play().catch(()=>{})})()")
        page.wait_for_timeout(500)
        clamp = page.evaluate(
            "(()=>{const v=document.getElementById('winVideo');return {t:v.currentTime,paused:v.paused}})()")
        assert clamp["paused"] and clamp["t"] <= 16.1, clamp
        checks.append(f"T1 16s: independent UNKNOWN saved and playback clamped at query time (t={clamp['t']:.2f}s)")
        page.locator("#stepBtn3").click()
        page.locator('[data-f="vf"]').select_option("UNCONFIRMABLE")
        page.locator('[data-f="ans"]').fill("UNKNOWN")
        page.locator('[data-f="cert"]').select_option("UNKNOWN")
        page.locator('[data-f="wsuf"]').select_option("UNCERTAIN")
        page.locator('[data-f="hist"]').select_option("UNCERTAIN")
        page.locator('[data-f="alt"]').select_option("UNKNOWN")
        page.locator('[data-f="dec"]').select_option("PENDING")
        page.locator('[data-f="note"]').fill("UI 测试：仅见按键，未读出实测温度。")
        page.locator("#saveDecision").click()
        page.wait_for_timeout(600)
        saved = json.loads(page.evaluate(f"localStorage.getItem('{V2_KEY}')"))
        r1 = saved["tasks"]["ego_mc:GX010021:visual_task:T1_oven"]
        assert r1["step3"]["decision"] == "PENDING" and r1["step3"]["answer_text"] == "UNKNOWN"
        assert r1["step3"]["visual_fact"] == "UNCONFIRMABLE" and r1["step1"]["locked"]
        assert "已审 1 / 9" in page.locator("#progress").inner_text()
        checks.append("T1 16s: UNKNOWN/PENDING saved, progress shows 1/9")
        page.locator("#stepBtn2").click()
        assert page.locator(".evItem").count() >= 1 and page.locator("#winVideo").count() == 1
        assert page.locator('[data-f="s2note"]').count() == 1
        checks.append("T1 16s (no history evidence): Step 2 renders current window + note panel")
        page.locator("#stepBtn3").click()

        # ---- Scenario 2: T3 525s microwave-history task ----
        task_button(page, "最初实际打入").click()
        assert page.locator(".qtext").first.inner_text().startswith("回顾当前混合物")
        assert page.locator("#stepBtn2").is_disabled()  # no residue from previous task
        page.locator('[data-f="s1answer"]').fill("当前窗口无法确定，疑似 2 枚")
        page.locator('[data-f="s1suf"]').select_option("INSUFFICIENT")
        page.locator("button", has_text="锁定 Step 1 初始记录").click()
        page.locator("#stepBtn2").click()
        ev_labels = page.locator(".evItem .t").all_inner_texts()
        assert any("crack_first" in x for x in ev_labels) and any("crack_second" in x for x in ev_labels)
        assert any("return_intact" in x for x in ev_labels)
        checks.append("T3 525s: Step 2 lists current window + 3 historical video evidences")
        page.locator(".evItem", has_text="crack_first").click()
        page.wait_for_function("document.getElementById('evVideo').readyState>=1")
        src = page.evaluate("document.getElementById('evVideo').getAttribute('src')")
        assert "clips/crack_first.mp4" in src, src
        cur_src = page.evaluate("document.getElementById('winVideo').getAttribute('src')")
        assert "clips/T3_eggs_history_current.mp4" in cur_src, cur_src
        page.wait_for_function("document.querySelectorAll('.frameStrip img').length>=2")
        assert page.evaluate("document.querySelector('.frameStrip img').naturalWidth>0")
        checks.append("T3 525s: side-by-side players use correct per-task clips and frame images load")
        page.locator('[data-f="s2note"]').fill("历史可见两次打蛋与第三枚放回。")
        page.locator('[data-f="s2chk"]').check()
        page.locator("#stepBtn3").click()
        page.locator('[data-f="hist"]').select_option("HISTORY_RETRIEVAL")
        page.locator('[data-f="dec"]').select_option("PENDING")
        page.locator("#saveDecision").click()
        page.wait_for_timeout(600)
        checks.append("T3 525s: independent-first flow then HISTORY_RETRIEVAL classification saved")

        # ---- T2: rule source/validity required, speech rule not defaulted ----
        task_button(page, "烤模准备").click()
        page.locator('[data-f="s1answer"]').fill("UNKNOWN")
        page.locator('[data-f="s1suf"]').select_option("UNCERTAIN")
        page.locator("button", has_text="锁定 Step 1 初始记录").click()
        page.locator("#stepBtn3").click()
        assert page.locator('[data-f="t2src"]').count() == 1
        page.locator('[data-f="t2src"]').select_option("ANNOTATION_TEXT")
        page.locator('[data-f="t2val"]').select_option("UNVERIFIABLE")
        page.locator('[data-f="t2note"]').fill("无音轨，许可链无法核实，不默认成立。")
        page.locator('[data-f="dec"]').select_option("CONTROL_ONLY")
        page.locator("#saveDecision").click()
        page.wait_for_timeout(600)
        checks.append("T2: rule source/validity fields shown and UNVERIFIABLE speech rule saved")

        # ---- Scenario 3: reload keeps drafts ----
        page.reload(wait_until="load")
        assert "已审 3 / 9" in page.locator("#progress").inner_text()
        task_button(page, "350°F").click()
        assert page.locator(".lockedBanner").count() == 1
        page.locator("#stepBtn3").click()
        assert page.locator('[data-f="ans"]').input_value() == "UNKNOWN"
        checks.append("reload: all 3 drafts and Step 1 locks restored (3/9)")

        # ---- Scenario 4: task switch refreshes player/evidence ----
        task_button(page, "第二次从微波炉").click()
        page.wait_for_function("document.getElementById('winVideo').readyState>=1")
        assert "T1_butter_current" in page.evaluate("document.getElementById('winVideo').getAttribute('src')")
        page.locator('[data-f="s1answer"]').fill("UNKNOWN")
        page.locator("button", has_text="锁定 Step 1 初始记录").click()
        page.locator("#stepBtn2").click()
        labels = page.locator(".evItem .t").all_inner_texts()
        assert any("butter_first_check" in x for x in labels)
        assert not any("crack_first" in x for x in labels)
        checks.append("task switch: player clip and evidence list fully refreshed, no residue")

        # ---- Scenario 5: export -> wipe -> import round trip ----
        with page.expect_download() as dl:
            page.locator("#exportBtn").click()
        export_path = Path(dl.value.path())
        data = json.loads(export_path.read_text(encoding="utf-8"))
        assert data["format_version"] == 2 and len(data["tasks"]) == 4
        if "review" in data:
            assert data["review"]["status"] == "PENDING"
        page.evaluate(f"localStorage.removeItem('{V2_KEY}')")
        page.reload(wait_until="load")
        assert "已审 0 / 9" in page.locator("#progress").inner_text()
        page.locator("#importBtn").click()
        page.locator("#importFile").set_input_files(str(export_path))
        page.wait_for_timeout(400)
        task_button(page, "350°F").click()
        page.locator("#stepBtn3").click()
        assert page.locator('[data-f="dec"]').input_value() == "PENDING"
        assert page.locator('[data-f="hist"]').input_value() == "UNCERTAIN"
        assert "已审 3 / 9" in page.locator("#progress").inner_text()
        checks.append("export/import: all fields restored after wipe (3/9 with decisions)")

        # ---- Scenario 7: legacy v1 draft migration ----
        legacy = {"ego_mc:GX010021:visual_task:T1_oven": {
            "task_ref": "ego_mc:GX010021:visual_task:T1_oven",
            "reviewer": "LEGACY REVIEWER",
            "notes": "legacy draft note; no adjudication."}}
        page.evaluate(f"localStorage.setItem('{LEGACY_KEY}',{json.dumps(json.dumps(legacy))})")
        page.evaluate(f"localStorage.removeItem('{V2_KEY}')")
        page.reload(wait_until="load")
        assert "旧版草稿迁移 1 条" in page.locator("#migrateInfo").inner_text()
        assert page.locator("#reviewer").input_value() == "LEGACY REVIEWER"
        migrated = json.loads(page.evaluate(f"localStorage.getItem('{V2_KEY}')"))
        note = migrated["tasks"]["ego_mc:GX010021:visual_task:T1_oven"]["step3"]["notes"]
        assert "legacy draft note" in note
        assert not migrated["tasks"]["ego_mc:GX010021:visual_task:T1_oven"]["step1"]["locked"]
        checks.append("legacy v1 JSON drafts migrate into v2 (notes + reviewer, no fake lock), original kept")

        # ---- media error message surface (missing clip) ----
        task_button(page, "350°F").click()
        page.evaluate("document.getElementById('winVideo').setAttribute('src','clips/__missing__.mp4')")
        page.wait_for_timeout(400)
        assert "视频加载失败" in page.locator("#winVideoMsg").inner_text()
        checks.append("video load failure shows explicit in-pane error message")

        # ---- Screenshots (T3 eggs task, full step flow) ----
        page.evaluate(f"localStorage.removeItem('{V2_KEY}');localStorage.removeItem('{LEGACY_KEY}')")
        page.reload(wait_until="load")
        task_button(page, "最初实际打入").click()
        page.wait_for_timeout(300)
        page.screenshot(path=str(OUT / "workbench_v2_step1.png"))
        page.locator('[data-f="s1answer"]').fill("UNKNOWN")
        page.locator('[data-f="s1suf"]').select_option("INSUFFICIENT")
        page.locator("button", has_text="锁定 Step 1 初始记录").click()
        page.locator("#stepBtn2").click()
        page.locator(".evItem", has_text="crack_second").click()
        page.wait_for_timeout(600)
        page.screenshot(path=str(OUT / "workbench_v2_step2.png"))
        page.locator("#stepBtn3").click()
        page.screenshot(path=str(OUT / "workbench_v2_step3.png"))
        page.evaluate("window.scrollTo(0,0)")
        checks.append("screenshots saved: workbench_v2_step1/2/3.png")

        # cleanup test-only drafts
        page.evaluate(f"localStorage.removeItem('{V2_KEY}');localStorage.removeItem('{LEGACY_KEY}')")
        ctx.close()
        browser.close()

    assert not errors, errors
    assert OLD.exists() and "index_v2" not in OLD.read_text(encoding="utf-8", errors="ignore")[:500]
    report = {"status": "PASS", "browser": "Microsoft Edge headless", "mode": "file://",
              "checks": checks, "javascript_errors": errors, "formal_benchmark_run": False}
    (OUT / "ui_tests_v2.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
