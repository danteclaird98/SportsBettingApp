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
            executable=os.environ.get('CHROMIUM_PATH') or ('/usr/bin/chromium' if Path('/usr/bin/chromium').is_file() else None)
            browser=p.chromium.launch(executable_path=executable,headless=True,args=['--no-sandbox'])
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
            page.get_by_role('button',name='Save research receipt',exact=True).click()
            page.get_by_role('button',name='Saved receipt #1',exact=True).wait_for()
            assert Workspace(Path(tmp)/'work.sqlite3').receiving60_records()['receipts'][0]['id']==1
            page.reload()
            page.locator('nav').get_by_role('button',name='Receiving 60+ lab',exact=False).click()
            page.get_by_role('button',name='View receipt #1',exact=True).click()
            with page.expect_download() as saved_download:
                page.get_by_role('button',name='Download saved receipt #1',exact=True).click()
            saved=json.loads(Path(saved_download.value.path()).read_text())
            assert saved['scoreReceipt']==receipt['scoreReceipt']
            assert saved['request']==receipt['request']
            assert saved['inputMode']=='synthetic'
            assert saved['inputModeProvenance']=='CLIENT_DECLARED'
            page.get_by_role('button',name='Load synthetic example').click()
            page.locator('[name=prior-0-receivingYards]').fill('-10')
            assert page.locator('[name=inputMode]').input_value()=='synthetic'
            page.get_by_role('button',name='Calculate research estimate').click()
            page.locator('.research-estimate').filter(has_text='%').wait_for()
            page.locator('[name=inputMode]').select_option('supplied')
            assert page.get_by_role('button',name='Download research receipt',exact=True).count()==0
            assert 'This draft began as a synthetic example.' in page.locator('#receiving60-form').inner_text()
            page.locator('[name=inputMode]').select_option('synthetic')
            page.get_by_role('button',name='Calculate research estimate').click()
            page.locator('.research-estimate').filter(has_text='%').wait_for()
            for _ in range(3):
                page.get_by_role('button',name='Remove game 1',exact=True).click()
            assert page.get_by_role('button',name='Download research receipt').count()==0
            page.get_by_role('button',name='Calculate research estimate').click()
            page.get_by_text('At least three prior games are required.',exact=True).wait_for()
            assert 'No estimate' in page.locator('#receiving60-result').inner_text()
            page.get_by_text('Import history JSON',exact=True).click()
            page.locator('[name=history]').fill('invalid JSON')
            page.get_by_role('button',name='Apply imported history',exact=True).click()
            page.locator('#receiving60-form .error').wait_for()
            assert page.get_by_role('button',name='Download research receipt').count()==0
            page.get_by_role('button',name='Clear inputs').click()
            assert page.locator('[name=playerId]').input_value()==''
            page.get_by_role('button',name='Add prior game',exact=True).click()
            assert page.locator('[name=prior-0-receivingYards]').count()==1
            page.get_by_role('button',name='Remove game 1',exact=True).click()
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
            page.get_by_role('button',name='Data & integrations',exact=False).click()
            page.get_by_label('Response format',exact=True).select_option('normalized')
            imported=[{'provider':'synthetic','event_id':'synthetic:1','event':'Away @ Home','league':'NFL','bookmaker':'example','selection':'Home','period':'full_game','rules':'unknown','market':'moneyline','decimal_price':2.0,'starts_at':'2026-11-01T20:00:00Z','source_market_id':'native','status':'open'}]
            page.get_by_label('Provider response JSON',exact=True).fill(json.dumps(imported))
            page.get_by_role('button',name='Save unverified observations',exact=True).click()
            page.get_by_text('Import saved · unverified research only',exact=False).wait_for()
            page.get_by_role('button',name='Save unverified observations',exact=True).click()
            page.get_by_text('Import saved · unverified research only',exact=False).wait_for()
            page.get_by_role('button',name='Reload saved imports',exact=True).click()
            page.get_by_text('Saved import evidence',exact=True).wait_for()
            assert '"observation_count": 1' in page.locator('#content').inner_text()
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), 'Import mobile viewport overflow'
            page.goto(f'http://127.0.0.1:{server.server_port}/advanced/')
            page.get_by_role('button',name='Independent model',exact=True).click()
            page.get_by_role('heading',name='Independent probability model',exact=True).wait_for()
            assert page.url.endswith('#model')
            page.reload()
            page.get_by_role('heading',name='Independent probability model',exact=True).wait_for()
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), 'Independent model mobile overflow'
            page.set_viewport_size({'width':1440,'height':1050})
            page.reload()
            page.get_by_role('heading',name='Independent probability model',exact=True).wait_for()
            assert page.url.endswith('#model')
            page.set_viewport_size({'width':390,'height':844})
            page.get_by_role('button',name='Advanced Research',exact=True).click()
            report_link=page.get_by_role('link',name='Open assistant JSON report',exact=True)
            assert report_link.get_attribute('href').startswith('/research-api/api/assistant-report?')
            page.get_by_role('button',name='Models & history',exact=True).click()
            page.get_by_role('heading',name='Receiving yards forecast',exact=True).wait_for()
            page.get_by_role('button',name='Load source-backed players & games',exact=True).wait_for()
            page.get_by_role('button',name='Inspect 2026 validation',exact=True).click()
            page.get_by_role('table',name='Frozen 2026 retrospective comparison — lower losses are better').wait_for()
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), 'Master forecast mobile viewport overflow'
            page.get_by_role('button',name='Bookmakers & diagnostics',exact=True).click()
            page.get_by_role('button',name='Check backend connection',exact=True).click()
            page.get_by_text('Backend not connected. Configure the owned HTTPS service and its server-side read token.',exact=True).wait_for()
            assert page.get_by_role('button',name='Load stored events',exact=True).is_disabled()
            # A deterministic intercepted failure exercises React's actual save/recovery workflow.
            # This ledger never writes to the test server, let alone a hosted/private account.
            ledger={'posts':0,'wagers':[]}
            def mock_ledger(route):
                if route.request.method=='POST':
                    ledger['posts']+=1
                    if ledger['posts']==1:
                        return route.fulfill(status=503,json={'error':'Synthetic unavailable acknowledgement'})
                    ledger['wagers']=route.request.post_data_json['wagers']
                    return route.fulfill(status=200,json={'count':len(ledger['wagers']),'updatedAt':'2026-10-25T00:00:00Z'})
                return route.fulfill(status=200,json={'wagers':ledger['wagers'],'updatedAt':None,'authenticated':True})
            page.route('**/research-api/api/wager-ledger',mock_ledger)
            page.get_by_role('button',name='My Wagers',exact=True).click()
            page.get_by_role('heading',name='Research wager ledger',exact=True).wait_for()
            sign_in=page.get_by_role('button',name='Sign in to track wagers',exact=True)
            if sign_in.count(): sign_in.click()
            page.get_by_text('Private ledger loaded. Changes save to your account.',exact=True).wait_for()
            page.get_by_role('button',name='Paper wager',exact=True).click()
            page.get_by_label('Event',exact=True).fill('Synthetic recovery fixture')
            page.get_by_label('Market',exact=True).fill('moneyline')
            page.get_by_label('Selection',exact=True).fill('Synthetic Home')
            save=page.get_by_role('button',name='Save manual paper wager',exact=True)
            save.click()
            page.get_by_text('Save could not be confirmed. Your draft is retained. Reload saved ledger before editing or retrying.',exact=True).wait_for()
            assert page.get_by_label('Event',exact=True).input_value()=='Synthetic recovery fixture'
            assert page.get_by_label('Selection',exact=True).input_value()=='Synthetic Home'
            assert save.is_disabled(), 'Unconfirmed write must require reload before retry'
            assert ledger['posts']==1, 'No automatic write retry permitted'
            page.get_by_role('button',name='Reload saved ledger',exact=True).click()
            page.get_by_text('Private ledger loaded. Changes save to your account.',exact=True).wait_for()
            assert page.get_by_label('Event',exact=True).input_value()=='Synthetic recovery fixture'
            save.click()
            page.get_by_text('Saved to your private account.',exact=True).wait_for()
            assert page.get_by_label('Event',exact=True).input_value()==''
            assert ledger['posts']==2 and len(ledger['wagers'])==1
            assert ledger['wagers'][0]['mode']=='paper'
            page.reload()
            page.get_by_text('Synthetic recovery fixture',exact=True).wait_for()
            assert page.url.endswith('#wagers')
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), 'Research ledger mobile overflow'
            page.unroute('**/research-api/api/wager-ledger',mock_ledger)
            page.get_by_role('link',name='Return to EdgeBoard workspace',exact=True).click()
            page.get_by_role('heading',name='A clearer view of the board.',exact=True).wait_for()
            assert not errors,errors
            print('PASS: desktop/mobile; independent-model hash reload; research wager failed-save draft retention/reload/recovery; demo filter; slip; price math; wager save/settle/persistence; five reports; seven sources; JSON download; receiving60 score/abstention/stale-result clearing/receipt persistence/reload/manual history/mobile; no JS errors')
            browser.close()
    finally:
        server.shutdown();server.server_close()
        child.terminate()
        child.wait(timeout=10)
