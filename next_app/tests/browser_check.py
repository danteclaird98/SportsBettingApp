"""End-to-end local check with a disposable database. Requires Playwright + Chromium."""
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from threading import Thread
from http.server import ThreadingHTTPServer
from playwright.sync_api import sync_playwright
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from next_app.server import Workspace, make_handler
from edgeodds.ingestion import IngestionStore

with TemporaryDirectory() as tmp:
    store=IngestionStore(Path(tmp)/'odds.sqlite3')
    server=ThreadingHTTPServer(('127.0.0.1',0),make_handler(Workspace(Path(tmp)/'work.sqlite3'),store,'browser-test'))
    Thread(target=server.serve_forever,daemon=True).start()
    try:
        with sync_playwright() as p:
            browser=p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox'])
            page=browser.new_page(viewport={'width':1440,'height':1050})
            errors=[]
            page.on('pageerror',lambda e:errors.append(str(e)))
            page.goto(f'http://127.0.0.1:{server.server_port}')
            page.get_by_text('Your board is waiting for source data.').wait_for()
            page.get_by_role('button',name='Explore demo board').click()
            page.get_by_text('Buffalo Bills',exact=True).first.wait_for()
            assert page.locator('tbody tr').count()==12
            page.get_by_role('button',name='NFL',exact=True).click()
            assert page.locator('tbody tr').count()==3
            page.get_by_role('button',name='+ Slip',exact=True).first.click()
            page.get_by_role('button',name='Check my slip',exact=False).first.click()
            page.get_by_text('Research slip · 1 selections').wait_for()
            page.get_by_role('button',name='Calculate two-way benchmark').click()
            assert '50.00%' in page.locator('#calc-result').inner_text()
            page.get_by_role('button',name='My wagers',exact=False).click()
            f=page.locator('#wager-form')
            f.locator('[name=book]').fill('Example')
            f.locator('[name=selection]').fill('Example A moneyline')
            f.get_by_role('button',name='Save wager').click()
            page.get_by_text('Example A moneyline',exact=True).wait_for()
            settle=page.locator('[data-settle]')
            settle.locator('[name=status]').select_option('win')
            settle.locator('[name=payout]').fill('19.10')
            settle.locator('[name=confirmed]').check()
            settle.get_by_role('button',name='Confirm').click()
            page.get_by_text('$9.10',exact=True).wait_for()
            page.reload()
            page.get_by_role('button',name='My wagers',exact=False).click()
            page.get_by_text('$9.10',exact=True).wait_for()
            page.get_by_role('button',name='Models & history',exact=False).click()
            page.get_by_text('NFL · corrected receiving 60+',exact=True).wait_for()
            assert page.locator('.modelcard').count()==5
            page.get_by_role('button',name='Data & integrations',exact=False).click()
            assert page.locator('.sourcecard').count()==7
            with page.expect_download() as download:
                page.get_by_role('button',name='Download workspace report').click()
            assert download.value.suggested_filename=='edgeboard-workspace.json'
            page.get_by_role('button',name='Market board',exact=False).click()
            page.locator('#mode').select_option('demo')
            page.get_by_text('Buffalo Bills',exact=True).first.wait_for()
            out=Path(__file__).resolve().parents[1]/'previews'; out.mkdir(exist_ok=True)
            page.screenshot(path=str(out/'desktop.png'),full_page=True)
            page.set_viewport_size({'width':390,'height':844})
            page.screenshot(path=str(out/'mobile.png'),full_page=True)
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), 'Mobile viewport overflow'
            assert not errors,errors
            print('PASS: desktop/mobile; demo filter; slip; price math; wager save/settle/persistence; five reports; seven sources; JSON download; no JS errors')
            browser.close()
    finally:
        server.shutdown();server.server_close()
