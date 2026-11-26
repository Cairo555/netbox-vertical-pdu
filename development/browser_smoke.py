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


def native_fingerprint(svg):
    """Compare actual native geometry, labels, role colors and theme colors."""
    svg.page.mouse.move(0, 0)
    svg.page.evaluate("document.activeElement?.blur()")
    return svg.evaluate("""svg => ({
        width: svg.getAttribute('width'), height: svg.getAttribute('height'),
        background: getComputedStyle(svg).backgroundColor,
        elements: [...svg.querySelectorAll('rect, text, image')].map(el => ({
            tag: el.tagName, text: el.textContent,
            attrs: [...el.attributes].map(a => [a.name, a.value]),
            fill: getComputedStyle(el).fill, stroke: getComputedStyle(el).stroke
        }))
    })""")


with sync_playwright() as p:
    browser = p.chromium.launch()
    context = browser.new_context(viewport={"width": 1600, "height": 1100}, color_scheme="light")
    page = context.new_page()
    page.on("pageerror", lambda error: errors.append(str(error)))
    try:
        login(page, "smoke-admin", "Disposable-admin-42!")
        page.goto(BASE + fixture["rack"])
        expect(page.locator(".rack_elevation > svg")).to_have_count(2)
        native_front = native_fingerprint(page.locator(".rack_elevation > svg").nth(0))
        native_rear = native_fingerprint(page.locator(".rack_elevation > svg").nth(1))
        page.get_by_role("link", name="Enhanced Rack Elevation", exact=True).click()
        expect(page.locator(".vpdu-scene")).to_be_visible()
        expect(page.locator(".vpdu-native > svg")).to_be_visible()
        assert native_fingerprint(page.locator(".vpdu-native > svg")) == native_rear
        assert context.request.get(BASE + "/static/netbox_vertical_pdu/elevation-v0.3.0.css").status == 200
        assert context.request.get(BASE + "/static/netbox_vertical_pdu/elevation-v0.3.0.js").status == 200
        record("Native rack tab and packaged stylesheet load in real Docker web server")

        boxes = []
        for name in ("PDU-L1", "PDU-L2", "PDU-R1", "PDU-R2"):
            element = page.locator(f'.vpdu-scene a[aria-label="{name}"] .vpdu-device')
            expect(element).to_have_count(1)
            box = element.bounding_box()
            assert box["width"] > 0 and box["height"] > 0
            boxes.append(box)
        assert boxes[0]["x"] == boxes[1]["x"] < boxes[2]["x"] == boxes[3]["x"]
        assert boxes[0]["y"] + boxes[0]["height"] < boxes[1]["y"]
        assert boxes[2]["y"] + boxes[2]["height"] < boxes[3]["y"]
        outlet_boxes = [el.bounding_box() for el in page.locator('.vpdu-pdu[data-device="PDU-L1"] .vpdu-socket').all()]
        assert len(outlet_boxes) == 13
        # Borders differ for occupied/free sockets; compare their centers.
        assert len({round(box["x"] + box["width"] / 2, 1) for box in outlet_boxes}) == 1
        assert all(a["y"] + a["height"] < b["y"] for a, b in zip(outlet_boxes, outlet_boxes[1:]))
        half = page.locator('.vpdu-native a').filter(has=page.locator('text', has_text="Half-U-shelf"))
        expect(half.locator("rect")).to_have_attribute("height", "11")
        row = page.locator("tbody tr").filter(has=page.get_by_role("link", name="PDU-L1", exact=True))
        expect(row.locator("td").nth(3)).to_have_text("3 / 10")
        assert page.locator(".vpdu-scene rect.vpdu-used").count() == 10
        record("Two stacked PDUs per side, vertical labeled sockets, half-U equipment and outlet occupancy")

        row.locator("summary").click()
        expect(row.get_by_role("link", name="Server-019", exact=True)).to_be_visible()
        expect(row.get_by_role("link", name="Server-018", exact=True)).to_be_visible()
        expect(row.get_by_role("link", name="PSU-1", exact=True)).to_have_count(2)
        row.screenshot(path=str(OUTPUT / "outlet-details.png"))
        row.locator("summary").click()
        expect(page.locator('.vpdu-mount')).to_have_count(0)
        record("Outlet details show connected devices and ports; no physical measurement lines are drawn")

        expect(page.locator('.vpdu-connection')).to_have_count(3)
        connection1 = page.locator(f'.vpdu-connection[data-outlet-id="{fixture["outlet1_id"]}"]')
        connection2 = page.locator(f'.vpdu-connection[data-outlet-id="{fixture["outlet2_id"]}"]')
        expect(connection1).to_have_attribute('href', fixture['cable_url'])
        expect(connection1.locator('title')).to_contain_text('PDU-L1 / Outlet-01 → Server-019 / PSU-1')
        target = page.locator('.vpdu-native a').filter(has=page.locator('text', has_text='Server-019')).locator('rect')
        target_box = target.bounding_box()
        endpoint = connection1.locator('circle').bounding_box()
        assert abs(endpoint['x'] + endpoint['width'] / 2 - target_box['x'] - 6) < 1.5
        assert abs(endpoint['y'] + endpoint['height'] / 2 - target_box['y'] - target_box['height'] / 2) < 1.5
        expect(connection1.locator('path')).not_to_have_attribute('stroke-dasharray', '6 4')
        record("A real outlet cable ends at the correct full-depth server on the opposite rack face")

        socket1 = page.locator(f'.vpdu-outlet[data-outlet-id="{fixture["outlet1_id"]}"]')
        socket2 = page.locator(f'.vpdu-outlet[data-outlet-id="{fixture["outlet2_id"]}"]')
        right_socket = page.locator(f'.vpdu-outlet[data-outlet-id="{fixture["right_outlet_id"]}"]')
        server19 = page.locator('.vpdu-native a').filter(has=page.locator('text', has_text='Server-019'))
        server18 = page.locator('.vpdu-native a').filter(has=page.locator('text', has_text='Server-018'))
        page.set_viewport_size({"width": 1600, "height": 2000})
        page.evaluate("window.scrollTo(0, 0)")
        socket1.locator('.vpdu-socket').hover()
        expect(connection1).to_have_class('vpdu-connection vpdu-highlight')
        expect(connection2).to_have_class('vpdu-connection')
        expect(server19).to_have_class('vpdu-highlight')
        expect(page.locator('.vpdu-outlet.vpdu-highlight')).to_have_count(1)
        assert connection2.evaluate('el => getComputedStyle(el).opacity') == '0.18'
        assert socket1.locator('.vpdu-socket').evaluate('el => getComputedStyle(el).stroke') == 'rgb(0, 107, 230)'
        expect(page.locator('.vpdu-highlight-overlay path')).to_have_count(1)
        assert page.locator('.vpdu-connections').evaluate("el => el.lastElementChild.matches('.vpdu-highlight-overlay')")
        assert page.locator('.vpdu-highlight-overlay path').evaluate('el => getComputedStyle(el).pointerEvents') == 'none'
        page.locator('.vpdu-scene').screenshot(path=str(OUTPUT / 'hover-outlet.png'))
        socket2.locator('.vpdu-socket').hover()
        expect(connection2).to_have_class('vpdu-connection vpdu-highlight')
        expect(connection1).to_have_class('vpdu-connection')
        expect(server18).to_have_class('vpdu-highlight')
        expect(server19).not_to_have_class('vpdu-highlight')
        server19.locator('rect').hover()
        expect(page.locator('.vpdu-connection.vpdu-highlight')).to_have_count(2)
        expect(socket1).to_have_class('vpdu-outlet vpdu-highlight')
        expect(right_socket).to_have_class('vpdu-outlet vpdu-highlight')
        expect(socket2).to_have_class('vpdu-outlet')
        expect(page.locator('.vpdu-highlight-overlay path')).to_have_count(2)
        page.locator('.vpdu-scene').screenshot(path=str(OUTPUT / 'hover-server.png'))
        page.mouse.move(0, 0)
        expect(page.locator('.vpdu-highlight')).to_have_count(0)
        expect(page.locator('.vpdu-highlight-overlay')).to_have_count(0)
        socket1.focus()
        expect(connection1).to_have_class('vpdu-connection vpdu-highlight')
        socket1.evaluate('el => el.blur()')
        expect(page.locator('.vpdu-highlight')).to_have_count(0)
        page.locator('.vpdu-pdu[data-device="PDU-L1"] .vpdu-outlet').nth(2).hover()
        expect(page.locator('.vpdu-highlight')).to_have_count(0)
        page.mouse.move(0, 0)
        page.set_viewport_size({"width": 1600, "height": 1100})
        record("Outlet/server hover isolates overlapping lines, highlights both feeds, paints on top, resets and supports keyboard focus")

        expect(page.locator("html")).to_have_attribute("data-bs-theme", "light")
        light_fill = page.locator(".vpdu-native rect.slot").first.evaluate("el => getComputedStyle(el).fill")
        page.screenshot(path=str(OUTPUT / "rack-light.png"), full_page=True)
        page.locator("button.color-mode-toggle:visible").first.click()
        expect(page.locator("html")).to_have_attribute("data-bs-theme", "dark")
        dark_fill = page.locator(".vpdu-native rect.slot").first.evaluate("el => getComputedStyle(el).fill")
        assert dark_fill != light_fill
        # Check persistence and capture without the native toggle's focus tooltip.
        page.reload()
        expect(page.locator("html")).to_have_attribute("data-bs-theme", "dark")
        expect(page.locator(".vpdu-native > svg")).to_be_visible()
        dark_native = native_fingerprint(page.locator(".vpdu-native > svg"))
        page.screenshot(path=str(OUTPUT / "rack-dark.png"), full_page=True)
        # Keep the whole drawing below the fixed navigation bar while taking
        # the focused screenshot; auto-scrolling a taller element clips its top.
        page.set_viewport_size({"width": 1600, "height": 2000})
        page.evaluate("window.scrollTo(0, 0)")
        page.locator(".vpdu-scene").screenshot(path=str(OUTPUT / "rack-diagram-dark.png"))
        socket1.locator('.vpdu-socket').hover()
        expect(connection1).to_have_class('vpdu-connection vpdu-highlight')
        assert page.locator('.vpdu-highlight-overlay path').evaluate('el => getComputedStyle(el).stroke') == 'rgb(114, 183, 255)'
        page.locator('.vpdu-scene').screenshot(path=str(OUTPUT / 'hover-outlet-dark.png'))
        page.mouse.move(0, 0)
        page.set_viewport_size({"width": 1600, "height": 1100})
        record("Native light/dark toggle changes SVG colors")

        page.goto(BASE + fixture["rack"])
        expect(page.locator(".rack_elevation > svg")).to_have_count(2)
        assert native_fingerprint(page.locator(".rack_elevation > svg").nth(1)) == dark_native
        page.goto(BASE + fixture["elevation"])
        expect(page.locator(".vpdu-native > svg")).to_be_visible()

        line = connection1.locator('path')
        line.scroll_into_view_if_needed()
        hit = line.evaluate("""el => {
            const p = el.getPointAtLength(4);
            const screen = new DOMPoint(p.x, p.y).matrixTransform(el.getScreenCTM());
            return {x: screen.x, y: screen.y};
        }""")
        page.mouse.click(hit['x'], hit['y'])
        page.wait_for_url(BASE + fixture['cable_url'])
        record("Clicking the connection line opens its native cable details")
        page.goto(BASE + fixture['elevation'])
        expect(page.locator('.vpdu-native > svg')).to_be_visible()

        # Outlet links now occupy the card body; the heading opens the device.
        page.locator('.vpdu-scene a[aria-label="PDU-L1"] .vpdu-heading').click()
        page.wait_for_url(BASE + fixture["pdu_url"])
        page.goto(BASE + fixture["elevation"])
        page.get_by_role("link", name="Front", exact=True).click()
        expect(page.locator('.vpdu-scene a[aria-label="PDU-F1"]')).to_have_count(1)
        expect(page.locator('.vpdu-scene a[aria-label="PDU-L1"]')).to_have_count(0)
        expect(page.locator(".vpdu-native > svg")).to_be_visible()
        page.locator("button.color-mode-toggle:visible").first.click()
        expect(page.locator("html")).to_have_attribute("data-bs-theme", "light")
        assert native_fingerprint(page.locator(".vpdu-native > svg")) == native_front
        page.reload()
        expect(page.locator(".vpdu-native > svg")).to_be_visible()
        page.screenshot(path=str(OUTPUT / "rack-front-native.png"), full_page=True)
        record("Front/rear SVG geometry, labels, colors and backgrounds match the native rack page exactly")
        short_pdu = page.locator('.vpdu-pdu[data-device="PDU-F1"]')
        expect(short_pdu.locator('.vpdu-outlet')).to_have_count(7)
        expect(short_pdu.locator('.vpdu-mount')).to_have_count(0)
        assert short_pdu.locator('.vpdu-outlet-name').all_text_contents() == [str(i) for i in range(7)]
        short_boxes = [el.bounding_box() for el in short_pdu.locator('.vpdu-socket').all()]
        assert all(a['y'] + a['height'] < b['y'] for a, b in zip(short_boxes, short_boxes[1:]))
        short_pdu.locator('.vpdu-outlet').first.click()
        page.wait_for_url(BASE + fixture['front_outlet_url'])
        record("All seven outlets on a short PDU remain visible in order and open their native outlet page")
        record("Clickable PDU and front/rear switching")

        page.goto(BASE + fixture["elevation"])
        page.get_by_role("link", name="Add vertical device", exact=True).click()
        expect(page.locator('.nav-tabs .nav-link.active')).to_have_text("Enhanced Rack Elevation")
        expect(page.locator('#id_device option').filter(has_text="PDU-L1")).to_have_count(0)
        expect(page.locator('#id_device option').filter(has_text="PDU-spare")).to_have_count(1)
        page.screenshot(path=str(OUTPUT / "add-vertical-device.png"), full_page=True)
        page.locator("#id_device").select_option(str(fixture["spare_id"]))
        page.locator("#id_side").select_option("right")
        page.locator("#id_lane").fill("3")
        page.locator("#id_height_u").fill("60")
        page.get_by_role("button", name="Save placement", exact=True).click()
        expect(page.locator("#page-content").get_by_text("The device must fit inside the rack:", exact=False)).to_be_visible()
        page.locator("#id_offset_u").fill("2")
        page.locator("#id_height_u").fill("12")
        page.get_by_role("button", name="Save placement", exact=True).click()
        expect(page.locator('.vpdu-scene a[aria-label="PDU-spare"]')).to_have_count(1)
        spare_row = page.locator("tbody tr").filter(has=page.get_by_role("link", name="PDU-spare", exact=True))
        spare_row.get_by_role("link", name="Edit", exact=True).click()
        expect(page.locator('.nav-tabs .nav-link.active')).to_have_text("Enhanced Rack Elevation")
        page.locator("#id_lane").fill("1")
        page.get_by_role("button", name="Save placement", exact=True).click()
        expect(page.locator("#page-content").get_by_text("This space is already occupied in the selected lane.", exact=True)).to_be_visible()
        page.locator("#id_lane").fill("3")
        page.locator("#id_height_u").fill("15")
        page.get_by_role("button", name="Save placement", exact=True).click()
        expect(page.locator('.vpdu-scene a[aria-label="PDU-spare"] .vpdu-device')).to_have_attribute("height", "330.0")
        spare_row.get_by_role("link", name="Remove", exact=True).click()
        expect(page.locator('.nav-tabs .nav-link.active')).to_have_text("Enhanced Rack Elevation")
        page.get_by_role("button", name="Remove placement", exact=True).click()
        expect(page.locator(".vpdu-scene")).to_be_visible()
        expect(page.locator('.vpdu-scene a[aria-label="PDU-spare"]')).to_have_count(0)
        assert context.request.get(BASE + fixture["spare_url"]).status == 200
        record("Browser create/edit/delete, bounds and overlap validation; core device retained")

        page.set_viewport_size({"width": 390, "height": 844})
        expect(page.locator(".vpdu-native > svg")).to_be_visible()
        page.evaluate("window.scrollTo(0, 0)")
        page.screenshot(path=str(OUTPUT / "rack-mobile.png"), full_page=True)
        assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1")
        assert page.locator(".vpdu-scroll").evaluate("el => el.scrollWidth > el.clientWidth")
        record("Mobile viewport contains wide elevation in horizontal scroll area")
        page.set_viewport_size({"width": 1600, "height": 1100})
        page.goto(BASE + fixture["descending"])
        expect(page.locator(".vpdu-native text.unit").first).to_have_text("11")
        expect(page.locator(".vpdu-native text.unit").last).to_have_text("28")
        page.screenshot(path=str(OUTPUT / "rack-descending.png"), full_page=True)
        record("Descending rack with non-default starting unit")

        reader_context = browser.new_context(viewport={"width": 1600, "height": 1100})
        reader = reader_context.new_page()
        reader.on("pageerror", lambda error: errors.append(str(error)))
        login(reader, "smoke-reader", "Disposable-reader-42!")
        reader.goto(BASE + fixture["elevation"])
        expect(reader.locator('.vpdu-native > svg')).to_be_visible()
        expect(reader.locator('.vpdu-pdu > a:not(.vpdu-outlet)')).to_have_count(1)
        for secret in ("PDU-L2", "PDU-R1", "PDU-R2", "Outlet-13", "Server-019"):
            assert secret not in reader.content()
        expect(reader.get_by_role("link", name="Add vertical device", exact=True)).to_have_count(0)
        expect(reader.locator('.vpdu-connection')).to_have_count(0)
        reader.locator('.vpdu-outlet').first.hover()
        expect(reader.locator('.vpdu-highlight-overlay')).to_have_count(0)
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
