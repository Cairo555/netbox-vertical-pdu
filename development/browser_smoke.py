"""Real Chromium checks against the disposable Docker stack, with reviewable screenshots."""
import json
from pathlib import Path

from playwright.sync_api import sync_playwright, expect

BASE = "http://127.0.0.1:8000"
OUTPUT = Path("test-results")
OUTPUT.mkdir(exist_ok=True)
fixture = json.loads((OUTPUT / "fixture.json").read_text())
checks = []
errors = []


def record(name):
    checks.append(name)
    print(f"PASS: {name}", flush=True)


def login(page, username, password):
    response = page.goto(BASE + "/login/")
    assert response.status == 200
    page.locator("#id_username").fill(username)
    page.locator("#id_password").fill(password)
    page.get_by_role("button", name="Sign In", exact=True).click()
    page.wait_for_url(BASE + "/")


with sync_playwright() as p:
    browser = p.chromium.launch()
    context = browser.new_context(viewport={"width": 1600, "height": 1100}, color_scheme="light")
    page = context.new_page()
    page.on("pageerror", lambda error: errors.append(str(error)))
    try:
        login(page, "smoke-admin", "Disposable-admin-42!")
        page.goto(BASE + fixture["rack"])
        page.get_by_role("link", name="Enhanced Rack Elevation", exact=True).click()
        expect(page.locator(".vpdu-scene")).to_be_visible()
        assert context.request.get(BASE + "/static/netbox_vertical_pdu/elevation.css").status == 200
        record("Native rack tab and packaged stylesheet load in real Docker web server")

        boxes = []
        for name in ("PDU-L1", "PDU-L2", "PDU-R1", "PDU-R2"):
            element = page.locator(f'.vpdu-scene a[aria-label="{name}"] .vpdu-device')
            expect(element).to_have_count(1)
            box = element.bounding_box()
            assert box["width"] > 0 and box["height"] > 0
            boxes.append(box)
        assert boxes[1]["x"] < boxes[0]["x"] < boxes[2]["x"] < boxes[3]["x"]
        assert abs(boxes[0]["height"] / boxes[2]["height"] - 38 / 42) < 0.001
        expect(page.locator('.vpdu-scene a[aria-label="Half-U-shelf"] .vpdu-device')).to_have_attribute("height", "14.0")
        row = page.locator("tbody tr").filter(has=page.get_by_role("link", name="PDU-L1", exact=True))
        expect(row.locator("td").nth(3)).to_have_text("3 / 10")
        assert page.locator(".vpdu-scene rect.vpdu-used").count() == 9
        record("Four lanes, physical heights, half-U equipment, cabled and marked outlet occupancy")

        expect(page.locator("html")).to_have_attribute("data-bs-theme", "light")
        light_fill = page.locator(".vpdu-rack").evaluate("el => getComputedStyle(el).fill")
        page.screenshot(path=str(OUTPUT / "rack-light.png"), full_page=True)
        page.locator("button.color-mode-toggle:visible").first.click()
        expect(page.locator("html")).to_have_attribute("data-bs-theme", "dark")
        dark_fill = page.locator(".vpdu-rack").evaluate("el => getComputedStyle(el).fill")
        assert dark_fill != light_fill
        page.mouse.move(300, 200)
        expect(page.locator(".tooltip.show")).to_have_count(0)
        page.screenshot(path=str(OUTPUT / "rack-dark.png"), full_page=True)
        record("Native light/dark toggle changes SVG colors")

        page.locator('.vpdu-scene a[aria-label="PDU-L1"]').click()
        page.wait_for_url(BASE + fixture["pdu_url"])
        page.goto(BASE + fixture["elevation"])
        page.get_by_role("link", name="Front", exact=True).click()
        expect(page.locator('.vpdu-scene a[aria-label="PDU-F1"]')).to_have_count(1)
        expect(page.locator('.vpdu-scene a[aria-label="PDU-L1"]')).to_have_count(0)
        record("Clickable PDU and front/rear switching")

        page.goto(BASE + fixture["elevation"])
        page.get_by_role("link", name="Add vertical device", exact=True).click()
        page.locator("#id_device").select_option(str(fixture["spare_id"]))
        page.locator("#id_side").select_option("right")
        page.locator("#id_lane").fill("3")
        page.locator("#id_height_u").fill("60")
        page.get_by_role("button", name="Save placement", exact=True).click()
        expect(page.get_by_text("The device must fit inside the rack:", exact=False)).to_be_visible()
        page.locator("#id_offset_u").fill("2")
        page.locator("#id_height_u").fill("12")
        page.get_by_role("button", name="Save placement", exact=True).click()
        expect(page.locator('.vpdu-scene a[aria-label="PDU-spare"]')).to_have_count(1)
        spare_row = page.locator("tbody tr").filter(has=page.get_by_role("link", name="PDU-spare", exact=True))
        spare_row.get_by_role("link", name="Edit", exact=True).click()
        page.locator("#id_lane").fill("1")
        page.get_by_role("button", name="Save placement", exact=True).click()
        expect(page.get_by_text("This space is already occupied in the selected lane.", exact=True)).to_be_visible()
        page.locator("#id_lane").fill("3")
        page.locator("#id_height_u").fill("15")
        page.get_by_role("button", name="Save placement", exact=True).click()
        expect(page.locator('.vpdu-scene a[aria-label="PDU-spare"] .vpdu-device')).to_have_attribute("height", "420.0")
        spare_row.get_by_role("link", name="Remove", exact=True).click()
        page.get_by_role("button", name="Remove placement", exact=True).click()
        expect(page.locator(".vpdu-scene")).to_be_visible()
        expect(page.locator('.vpdu-scene a[aria-label="PDU-spare"]')).to_have_count(0)
        assert context.request.get(BASE + fixture["spare_url"]).status == 200
        record("Browser create/edit/delete, bounds and overlap validation; core device retained")

        page.set_viewport_size({"width": 390, "height": 844})
        page.screenshot(path=str(OUTPUT / "rack-mobile.png"), full_page=True)
        assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1")
        assert page.locator(".vpdu-scroll").evaluate("el => el.scrollWidth > el.clientWidth")
        record("Mobile viewport contains wide elevation in horizontal scroll area")
        page.set_viewport_size({"width": 1600, "height": 1100})
        page.goto(BASE + fixture["descending"])
        expect(page.locator(".vpdu-scene > svg text").first).to_have_text("11")
        expect(page.locator(".vpdu-scene > svg text").last).to_have_text("28")
        page.screenshot(path=str(OUTPUT / "rack-descending.png"), full_page=True)
        record("Descending rack with non-default starting unit")

        reader_context = browser.new_context(viewport={"width": 1600, "height": 1100})
        reader = reader_context.new_page()
        reader.on("pageerror", lambda error: errors.append(str(error)))
        login(reader, "smoke-reader", "Disposable-reader-42!")
        reader.goto(BASE + fixture["elevation"])
        expect(reader.locator('.vpdu-scene > a')).to_have_count(1)
        for secret in ("PDU-L2", "PDU-R1", "PDU-R2", "Secret-outlet", "Compute-01"):
            assert secret not in reader.content()
        expect(reader.get_by_role("link", name="Add vertical device", exact=True)).to_have_count(0)
        expect(reader.locator("tbody tr td").nth(3)).to_have_text("2 / 0")
        reader.screenshot(path=str(OUTPUT / "rack-restricted.png"), full_page=True)
        record("Restricted user sees only permitted device/outlets and no edit controls")
        assert not errors, errors
        record("No uncaught browser JavaScript errors")
    except Exception:
        page.screenshot(path=str(OUTPUT / "failure.png"), full_page=True)
        raise
    finally:
        (OUTPUT / "browser-report.json").write_text(json.dumps({"passed": checks, "javascript_errors": errors}, indent=2))
        browser.close()
