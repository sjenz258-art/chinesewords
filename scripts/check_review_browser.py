"""Developer-only end-to-end check, self-contained local server and temporary DB."""
from pathlib import Path
import os
import subprocess
import sys
import tempfile
import time
import urllib.request
from playwright.sync_api import sync_playwright

root=Path(__file__).resolve().parent.parent
with tempfile.TemporaryDirectory() as directory:
    env=dict(os.environ,DATABASE_PATH=str(Path(directory)/'browser.sqlite'))
    env.pop('OPENAI_API_KEY',None)
    with (Path(directory)/'server.log').open('w') as log:
        server=subprocess.Popen([sys.executable,'-m','streamlit','run',str(root/'app.py'),
            '--server.headless','true','--server.port','8517','--browser.gatherUsageStats','false'],cwd=root,env=env,stdout=log,stderr=log)
        try:
            for _ in range(60):
                try:
                    urllib.request.urlopen('http://127.0.0.1:8517/_stcore/health',timeout=.5).close()
                    break
                except OSError:
                    time.sleep(.2)
            with sync_playwright() as p:
                browser=p.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox'])
                page=browser.new_page(viewport={'width':1100,'height':900})
                page.goto('http://127.0.0.1:8517')
                page.get_by_role('button',name='載入原創示例故事',exact=True).click()
                page.locator('.story').wait_for()
                page.get_by_role('button',name='儲存至書庫',exact=True).click()
                def navigate(label):
                    collapsed=page.get_by_test_id('stSidebarCollapsedControl')
                    if collapsed.is_visible(): collapsed.click()
                    page.get_by_test_id('stSidebar').get_by_text(label,exact=True).click()
                navigate('備份與說明')
                with page.expect_download() as download_info:
                    page.get_by_role('button',name='下載完整 JSON 備份（可在手機還原）',exact=True).click()
                backup=Path(directory)/'full.json'
                download_info.value.save_as(backup)
                page.get_by_test_id('stFileUploader').filter(has_text='還原完整 JSON').locator('input[type=file]').set_input_files(backup)
                page.get_by_text('我已下載目前備份，確認以此備份取代全部資料',exact=True).click()
                page.get_by_role('button',name='還原完整資料',exact=True).click()
                page.get_by_text('完整資料已還原。請前往閱讀書庫。',exact=True).wait_for()
                navigate('閱讀書庫')
                page.get_by_role('heading',name='小鳥的雨天朋友',exact=True).wait_for()
                page.set_viewport_size({'width':390,'height':844})
                page.locator('.story').scroll_into_view_if_needed()
                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
                page.get_by_text('點按才顯示拼音',exact=True).click()
                page.locator('.story.mode-tap').wait_for()
                first=page.locator('.story .reading-token').first
                second=page.locator('.story .reading-token').nth(1)
                first.locator('summary').click()
                assert first.locator('rt').evaluate('(e)=>getComputedStyle(e).visibility')=='visible'
                second.locator('summary').click()
                assert not first.evaluate('(e)=>e.open')
                tip=second.locator('.word-tip').bounding_box()
                assert 0<=tip['x'] and tip['x']+tip['width']<=390
                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
                page.screenshot(path=str(root/'samples/previews/review-mobile.png'))
                second.locator('summary').click()
                browser.close()
                print('PASS: full JSON download/upload/restore, library, 390px viewport, exclusive tap reveal, tooltip bounds.')
        finally:
            server.terminate()
            try: server.wait(timeout=5)
            except subprocess.TimeoutExpired: server.kill()
