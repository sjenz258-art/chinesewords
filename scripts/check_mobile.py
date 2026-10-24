"""Developer-only visual check: needs Playwright and system Chromium."""
from pathlib import Path
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser=p.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox'])
    page=browser.new_page(viewport={'width':390,'height':844},device_scale_factor=1)
    page.goto('http://localhost:8501')
    page.get_by_text('創作與修改',exact=True).wait_for()
    page.get_by_role('button',name='載入原創示例故事',exact=True).click()
    page.locator('.story').wait_for()
    page.locator('.story').scroll_into_view_if_needed()
    page.screenshot(path='samples/previews/mobile-pinyin.png')
    assert page.locator('.story ruby').count() > 100
    assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth')
    page.get_by_text('點按才顯示拼音',exact=True).click()
    page.wait_for_timeout(400)
    first=page.locator('.story .reading-token').first
    assert first.locator('rt').evaluate('(e)=>getComputedStyle(e).visibility') == 'hidden'
    first.locator('summary').click()
    assert first.locator('rt').evaluate('(e)=>getComputedStyle(e).visibility') == 'visible'
    first.locator('summary').click()
    assert first.locator('rt').evaluate('(e)=>getComputedStyle(e).visibility') == 'hidden'
    page.get_by_text('只看漢字',exact=True).click()
    page.wait_for_timeout(400)
    assert page.locator('.story rt').first.evaluate('(e)=>getComputedStyle(e).display') == 'none'
    page.screenshot(path='samples/previews/mobile-chinese.png')
    print('390px mobile view: ruby, tap/reveal/hide, Chinese-only, no horizontal overflow passed.')
    browser.close()
