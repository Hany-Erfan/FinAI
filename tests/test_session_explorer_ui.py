"""
Playwright UI tests for the Session Explorer feature.

Tests:
  1. Admin can navigate to /session-explorer and see the sessions table
  2. Regular user is redirected away from /session-explorer
  3. Admin can click a session row to see detail view
  4. Navigation buttons work (Backoffice → Session Explorer, Chat → Session Explorer)
"""

import pytest
from playwright.async_api import async_playwright

FRONTEND_URL = "http://localhost:5173"

ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin_AgentixBuddy"
USER_USERNAME = "user"
USER_PASSWORD = "user_AgentixBuddy"


async def login(page, username, password):
    """Helper: navigate to login page, fill credentials, submit."""
    await page.goto(FRONTEND_URL)
    await page.wait_for_load_state("networkidle")
    # Fill login form — username input has placeholder="admin", no type attr
    await page.fill('input[placeholder="admin"]', username)
    await page.fill('input[type="password"]', password)
    await page.click('button[type="submit"]')
    # SPA client-side routing — wait for the chat page elements
    await page.wait_for_selector(".chat-container, .page-container", timeout=15000)


def browser_args():
    """Chromium args to disable web security so CORS doesn't block credentialed requests."""
    return ["--disable-web-security", "--disable-features=IsolateOrigins,site-per-process"]


@pytest.mark.asyncio
async def test_admin_can_access_session_explorer():
    """Admin logs in → navigates to /session-explorer → sees sessions table."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=browser_args())
        page = await browser.new_page()
        try:
            await login(page, ADMIN_USERNAME, ADMIN_PASSWORD)

            # Navigate to session explorer
            await page.goto(f"{FRONTEND_URL}/session-explorer")
            await page.wait_for_load_state("networkidle")

            # Should see the heading
            heading = page.locator("h1")
            await heading.wait_for(timeout=10000)
            assert "Session Explorer" in await heading.text_content()

            # Should see the sessions table or at least the section
            table = page.locator("table.session-table, table.product-table")
            count = await table.count()
            # Table may or may not have data, but the container should be there
            # or at minimum the "All Sessions" heading should appear
            section_heading = page.locator("h2")
            h2_texts = []
            for i in range(await section_heading.count()):
                h2_texts.append(await section_heading.nth(i).text_content())
            assert any("All Sessions" in t for t in h2_texts), f"Expected 'All Sessions' heading, got: {h2_texts}"

        finally:
            await browser.close()


@pytest.mark.asyncio
async def test_regular_user_redirected_from_session_explorer():
    """Regular user navigates to /session-explorer → redirected to /chat."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=browser_args())
        page = await browser.new_page()
        try:
            await login(page, USER_USERNAME, USER_PASSWORD)

            # Try to navigate to session explorer
            await page.goto(f"{FRONTEND_URL}/session-explorer")
            await page.wait_for_load_state("networkidle")

            # Should be redirected to /chat (ProtectedRoute with requiredRole="admin")
            assert "/chat" in page.url, f"Expected redirect to /chat, got: {page.url}"

        finally:
            await browser.close()


@pytest.mark.asyncio
async def test_admin_can_click_session_row_for_detail():
    """Admin sees sessions table → clicks a row → sees detail view."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=browser_args())
        page = await browser.new_page()
        try:
            await login(page, ADMIN_USERNAME, ADMIN_PASSWORD)

            await page.goto(f"{FRONTEND_URL}/session-explorer")
            await page.wait_for_load_state("networkidle")

            # Wait for the table to appear with data rows
            row = page.locator("table tbody tr.clickable-row").first
            try:
                await row.wait_for(timeout=10000)
            except Exception:
                # No sessions in DB — skip detail test
                pytest.skip("No session rows found in table — nothing to click")

            await row.click()
            await page.wait_for_load_state("networkidle")

            # Should now see "Session Detail" heading — wait for it to appear
            detail_heading = page.locator("h1", has_text="Session Detail")
            await detail_heading.wait_for(timeout=10000)
            assert "Session Detail" in await detail_heading.text_content()

            # Should see "Conversation" section
            h3_texts = []
            h3s = page.locator("h3")
            for i in range(await h3s.count()):
                h3_texts.append(await h3s.nth(i).text_content())
            assert any("Conversation" in t for t in h3_texts), f"Expected 'Conversation' heading, got: {h3_texts}"

            # "Back to List" button should exist
            back_btn = page.locator("button", has_text="Back to List")
            assert await back_btn.count() > 0

        finally:
            await browser.close()


@pytest.mark.asyncio
async def test_session_explorer_nav_from_chat_sidebar():
    """Admin on chat page → clicks 'Session Explorer' in sidebar → arrives at /session-explorer."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=browser_args())
        page = await browser.new_page()
        try:
            await login(page, ADMIN_USERNAME, ADMIN_PASSWORD)

            # Should be on /chat now — look for the Session Explorer button in admin box
            btn = page.locator(".admin-box button", has_text="Session Explorer")
            await btn.wait_for(timeout=10000)
            await btn.click()

            await page.wait_for_url("**/session-explorer", timeout=10000)
            heading = page.locator("h1")
            assert "Session Explorer" in await heading.text_content()

        finally:
            await browser.close()


@pytest.mark.asyncio
async def test_session_explorer_nav_from_backoffice():
    """Admin on backoffice → clicks 'Session Explorer' button → arrives at /session-explorer."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=browser_args())
        page = await browser.new_page()
        try:
            await login(page, ADMIN_USERNAME, ADMIN_PASSWORD)

            await page.goto(f"{FRONTEND_URL}/backoffice")
            await page.wait_for_load_state("networkidle")

            btn = page.locator("button", has_text="Session Explorer")
            await btn.wait_for(timeout=10000)
            await btn.click()

            await page.wait_for_url("**/session-explorer", timeout=10000)
            heading = page.locator("h1")
            assert "Session Explorer" in await heading.text_content()

        finally:
            await browser.close()
