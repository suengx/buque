#!/usr/bin/env python3
"""诊断积加 ERP 登录表单与库存页。cd backend && uv run python scripts/diagnose_erp_page.py"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from buque.config import get_settings
from buque.ingestion.erp_selectors import PATHS
from playwright.sync_api import sync_playwright

settings = get_settings()
OUT = Path(__file__).resolve().parents[1] / "data" / "probe_debug"
OUT.mkdir(parents=True, exist_ok=True)


def dump_inputs(page) -> None:
    for sel in ['input[type="text"]', 'input[type="password"]', 'input', 'button']:
        loc = page.locator(sel)
        n = loc.count()
        if n:
            print(f"  {sel}: count={n}")
            for i in range(min(n, 5)):
                el = loc.nth(i)
                attrs = {
                    "type": el.get_attribute("type"),
                    "name": el.get_attribute("name"),
                    "placeholder": el.get_attribute("placeholder"),
                    "id": el.get_attribute("id"),
                    "class": (el.get_attribute("class") or "")[:80],
                }
                text = el.inner_text() if sel == "button" else ""
                print(f"    [{i}] {attrs} text={text!r}")


def main() -> None:
    base = settings.erp_base_url.rstrip("/")
    login_urls = [
        f"{base}/auth/login",
        f"{base}/login",
        f"{base}/login#/login",
        f"{base}/amzv-web/login",
    ]

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_context().new_page()

        for login_url in login_urls:
            print(f"\n=== LOGIN URL: {login_url}")
            page.goto(login_url, timeout=30000)
            page.wait_for_load_state("domcontentloaded")
            print("title:", page.title(), "url:", page.url)
            dump_inputs(page)
            page.screenshot(path=str(OUT / "login.png"))

            # 尝试填写：按 placeholder / type
            user = page.locator(
                'input[placeholder*="账号"], input[placeholder*="手机"], input[placeholder*="用户"], input[type="text"]'
            ).first
            pwd = page.locator('input[type="password"]').first
            if user.count() and pwd.count():
                user.fill(settings.erp_username)
                pwd.fill(settings.erp_password)
                btn = page.locator('button:has-text("登录"), button[type="submit"]').first
                print("click login, btn count:", btn.count())
                if btn.count():
                    btn.click()
                    try:
                        page.wait_for_load_state("networkidle", timeout=20000)
                    except Exception:
                        pass
                    print("after login url:", page.url)
                    page.screenshot(path=str(OUT / "after_login.png"))
                    if "login" not in page.url.lower():
                        print("LOGIN OK via", login_url)
                        break

        inv_paths = [
            f"{base}/amzv-web{PATHS.inventory_product}",
            f"{base}{PATHS.inventory_product}",
        ]
        for inv in inv_paths:
            print(f"\n=== INVENTORY: {inv}")
            page.goto(inv, timeout=30000)
            try:
                page.wait_for_load_state("networkidle", timeout=15000)
            except Exception:
                pass
            print("url:", page.url, "title:", page.title())
            dump_inputs(page)
            texts = page.get_by_text("导出", exact=False).all_inner_texts()
            print("export texts:", texts[:15])
            page.screenshot(path=str(OUT / "inventory.png"))

        browser.close()


if __name__ == "__main__":
    main()
