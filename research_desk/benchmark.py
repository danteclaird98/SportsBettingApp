"""Reproducible synthetic storage benchmark; never measures provider latency."""
import json,tempfile,time,sqlite3
from datetime import datetime,timedelta,timezone
from engine import Store

def run(count=2000):
    instant=datetime.now(timezone.utc);observed=instant.isoformat()
    with tempfile.TemporaryDirectory() as directory:
        store=Store(directory+'/db')
        quotes=[dict(id=str(i),provider='fixture',provider_event_id='fixture',event_id='fixture',sport='test',league='test',event='Synthetic',start_at=(instant+timedelta(days=1)).isoformat(),market='moneyline_2way',selection='selection:'+str(i),period='full',rules='fixture',sportsbook='book',observed_at=observed,retrieved_at=observed,decimal_odds=2,source_ref='synthetic',scope='pregame',status='open',provenance='demonstration') for i in range(count)]
        start=time.perf_counter();store.bulk_quotes('bench',quotes);ingest=time.perf_counter()-start
        start=time.perf_counter();page=store.odds_page('bench',limit=100);latest=time.perf_counter()-start
        start=time.perf_counter();history=store.odds_page('bench',latest=False,event_id='fixture',limit=100);elapsed=time.perf_counter()-start
        with sqlite3.connect(store.path) as c:
            plans={name:[list(r) for r in c.execute(sql,args)] for name,sql,args in [
                ('event_history','EXPLAIN QUERY PLAN SELECT * FROM quote_lookup WHERE user=? AND event_id=? ORDER BY seq LIMIT 100',('bench','fixture')),
                ('latest_lookup','EXPLAIN QUERY PLAN SELECT * FROM quote_lookup WHERE user=? AND book_key=? ORDER BY observed DESC LIMIT 1',('bench','key')),
                ('audit','EXPLAIN QUERY PLAN SELECT * FROM audit WHERE user=? ORDER BY sequence LIMIT 100',('bench',))]}
        return dict(synthetic_quotes=count,ingest_seconds=ingest,latest_page_seconds=latest,history_page_seconds=elapsed,latest_page_rows=len(page['items']),history_page_rows=len(history['items']),query_plans=plans)
if __name__=='__main__':print(json.dumps(run(),indent=2))
