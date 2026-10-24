"""End-to-end local check with a disposable database. Requires Playwright + Chromium."""
import json
import os
import subprocess
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
    runtime=Path(__file__).resolve().parents[1]/'research_runtime'
    child=subprocess.Popen(['node','runtime.mjs'],cwd=runtime,env=dict(os.environ,RESEARCH_DB=str(Path(tmp)/'research.sqlite3')),stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
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
            page.locator('nav').get_by_role('button',name='Receiving 60+ lab',exact=False).click()
            page.get_by_text('Artifact integrity: verified',exact=False).wait_for()
            page.get_by_role('button',name='Load synthetic example').click()
            page.get_by_role('button',name='Calculate research estimate').click()
            page.locator('.research-estimate').filter(has_text='%').wait_for()
            assert 'SYNTHETIC EXAMPLE' in page.locator('#receiving60-result').inner_text()
            with page.expect_download() as receipt_download:
                page.get_by_role('button',name='Download research receipt').click()
            receipt=json.loads(Path(receipt_download.value.path()).read_text())
            assert receipt['inputMode']=='synthetic'
            assert receipt['request']['request']['playerId']=='synthetic-player'
            assert receipt['scoreReceipt']['status']=='HOLD'
            assert receipt['scoreReceipt']['liveApproved'] is False
            assert 0<=receipt['scoreReceipt']['probability']<=1
            assert receipt['scoreReceipt']['features']==[45,45,2/3,2/3,3]
            page.locator('[name=history]').fill('[]')
            assert page.get_by_role('button',name='Download research receipt').count()==0
            page.get_by_role('button',name='Calculate research estimate').click()
            page.get_by_text('At least three prior games are required.',exact=True).wait_for()
            assert 'No estimate' in page.locator('#receiving60-result').inner_text()
            page.locator('[name=history]').fill('invalid JSON')
            page.get_by_role('button',name='Calculate research estimate').click()
            page.locator('#receiving60-form .error').wait_for()
            assert page.get_by_role('button',name='Download research receipt').count()==0
            page.get_by_role('button',name='Clear inputs').click()
            assert page.locator('[name=playerId]').input_value()==''
            assert 'SUPPLIED / UNVERIFIED' in page.locator('#content').inner_text()
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
            page.locator('nav').get_by_role('button',name='Receiving 60+ lab',exact=False).click()
            page.get_by_role('button',name='Load synthetic example').click()
            page.get_by_role('button',name='Calculate research estimate').click()
            page.locator('.research-estimate').filter(has_text='%').wait_for()
            page.screenshot(path=str(out/'receiving60-mobile.png'),full_page=True)
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), 'Receiving60 mobile viewport overflow'
            assert not errors,errors
            print('PASS: desktop/mobile; demo filter; slip; price math; wager save/settle/persistence; five reports; seven sources; JSON download; receiving60 score/abstention/stale-result clearing/receipt/mobile; no JS errors')
            browser.close()
    finally:
        server.shutdown();server.server_close()
        child.terminate()
        child.wait(timeout=10)
