"""Provider adapters. Retrieval proves observation, never executable availability or EV.

The Odds API v4 documentation: https://the-odds-api.com/liveapi/guides/v4/
No provider credentials or raw exception text enter records or diagnostics.
"""
import json
import os
import re
import threading
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from engine import now, timestamp, number, digest, required, text_fields
from core import proportional_no_vig


class ProviderError(ValueError):
    pass


def identifier(value):
    if not isinstance(value,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,160}',value):
        raise ValueError('Invalid provider identifier')
    return value


def line_text(value):
    if value is None: return None
    n=number(value,-1e12)
    return format(Decimal(str(n)).normalize(),'f') if n else '0'


def market_family(key, outcomes):
    if key.endswith('_lay'): return None  # Lay stakes, liabilities and exchange fees need another adapter.
    if key=='outrights': return 'futures'
    if key=='h2h': return 'moneyline_3way' if len(outcomes)==3 else 'moneyline_2way'
    if key=='h2h_3_way': return 'moneyline_3way'
    if key=='draw_no_bet': return 'moneyline_2way'
    if key=='spreads': return 'spread'
    if key=='alternate_spreads': return 'alternate_spread'
    if key=='totals': return 'total'
    if key=='alternate_totals': return 'alternate_total'
    if key.startswith(('team_totals','alternate_team_totals')): return 'team_total'
    if key.startswith(('player_','batter_','pitcher_')): return 'player_prop'
    if re.search(r'_(h[12]|q[1-4]|p[1-3]|1st_[1357]_innings|s[1-9][0-9]*)$',key): return 'period'
    return 'game_prop'  # Exact upstream key retained; unfamiliar rules stay unverified.


def normalize_odds(payload, retrieved_at, provenance='authorized_import'):
    """Normalize decimal-format provider responses; reject malformed whole snapshots.

    The provider does not supply account availability or book rule versions. Presence
    therefore produces unknown status and unverified rules. No parent timestamp fallback.
    """
    timestamp(retrieved_at)
    events=[payload] if isinstance(payload,dict) else payload
    if not isinstance(events,list): raise ValueError('Expected provider events array or event object')
    quotes=[]; skipped=[]
    for event in events:
        required(event,['id','sport_key','commence_time','bookmakers'])
        eid=identifier(event['id']); sport=identifier(event['sport_key']); start=timestamp(event['commence_time'])
        if not isinstance(event['bookmakers'],list): raise ValueError('Invalid bookmakers')
        title=' at '.join(event[k] for k in ['away_team','home_team'] if isinstance(event.get(k),str) and event[k]) or event.get('sport_title',sport)
        for book in event['bookmakers']:
            required(book,['key','title','markets']); bid=identifier(book['key'])
            if not isinstance(book['markets'],list): raise ValueError('Invalid markets')
            for market in book['markets']:
                required(market,['key','outcomes']); key=identifier(market['key'])
                outcomes=market['outcomes']
                if not isinstance(outcomes,list) or not outcomes: raise ValueError('Invalid outcomes')
                family=market_family(key,outcomes)
                if family is None:
                    skipped.append({'market':key,'reason':'Lay/exchange liability model unavailable'}); continue
                observation=market.get('last_update')
                if observation:
                    timestamp(observation)
                    if timestamp(observation)>timestamp(retrieved_at): raise ValueError('Future market observation')
                contract_rows=[]
                for outcome in outcomes:
                    required(outcome,['name','price']); text_fields(outcome,['name'])
                    price=number(outcome['price'],1)
                    if price<=1: raise ValueError('Decimal odds must exceed one')
                    participant=outcome.get('description')
                    if family=='player_prop' and participant is None and outcome['name'] not in ['Over','Under','Yes','No']: participant=outcome['name']
                    if family in ['player_prop','team_total'] and participant is None: raise ValueError('Participant identity missing for player/team contract')
                    if participant is not None and (not isinstance(participant,str) or not participant.strip()): raise ValueError('Invalid participant description')
                    line=line_text(outcome.get('point'))
                    if (family in ['spread','alternate_spread','total','alternate_total','team_total'] or key.startswith(('spreads_','alternate_spreads_','totals_','alternate_totals_'))) and line is None: raise ValueError('Line missing')
                    record=dict(provider='the_odds_api',provider_event_id=eid,event_id='the_odds_api:'+sport+':'+eid,
                        sport=event.get('sport_title',sport),league=sport,event=title,start_at=start.isoformat(),
                        market=family,market_key=key,participant_id=participant,selection=outcome['name'],line=line,
                        period='provider_market:'+key,rules='unverified:'+bid+':'+key,rules_verified=False,
                        sportsbook=bid,sportsbook_name=book['title'],observed_at=observation,retrieved_at=retrieved_at,
                        source_ref='The Odds API v4 event '+eid+' / '+bid+' / '+key,decimal_odds=price,
                        status='unknown',scope='live' if start<=timestamp(retrieved_at) and family!='futures' else 'pregame',
                        provenance=provenance,latency_seconds=None,availability='unknown',
                        source_payload_hash=digest(event),benchmark_probability=None,market_margin=None)
                    contract_rows.append(record)
                # A priced subset is not a complete outright or generic proposition market.
                groups={}
                for record in contract_rows:
                    is_spread=family in ['spread','alternate_spread'] or key.startswith(('spreads_','alternate_spreads_'))
                    group=(record['participant_id'],abs(Decimal(record['line'])) if is_spread else record['line'])
                    groups.setdefault(group,[]).append(record)
                for rows in groups.values():
                    names={r['selection'] for r in rows}
                    complete=False
                    if key=='draw_no_bet' or key.startswith('h2h'):
                        teams={event.get('home_team'),event.get('away_team')}
                        counts=[3] if key.startswith('h2h_3_way') else [2] if key=='draw_no_bet' else [2,3]
                        complete=len(rows) in counts and len(names)==len(rows) and teams<=names and (len(rows)==2 or names-teams in [{'Draw'},{'Tie'}])
                    elif is_spread:
                        complete=len(rows)==2 and names=={event.get('home_team'),event.get('away_team')} and sum(Decimal(r['line']) for r in rows)==0
                    elif family in ['total','alternate_total','team_total','player_prop'] or key.startswith(('totals_','alternate_totals_')):
                        complete=len(rows)==2 and names=={'Over','Under'}
                    if complete:
                        ps=proportional_no_vig([r['decimal_odds'] for r in rows],'decimal')
                        margin=sum(1/r['decimal_odds'] for r in rows)-1
                        for row,p in zip(rows,ps):
                            row.update(benchmark_probability=p,market_margin=margin,benchmark_method='same-book proportional normalization; conditional on decisive outcome where push is possible; unverified settlement rules')
                for record in contract_rows:
                    record['id']='odds:'+digest(record)
                    quotes.append(record)
    return {'quotes':quotes,'skipped':skipped}


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs): return None


class OddsAPI:
    provider_id='the_odds_api'
    def __init__(self, key=None, transport=None):
        self.key=key if key is not None else os.environ.get('ODDS_API_KEY','')
        self.transport=transport
        self.lock=threading.RLock(); self.retry_at=None; self.last_result='not_checked'; self.quota={}
    def health(self):
        return {'provider':self.provider_id,'configured':bool(self.key),'last_result':self.last_result,
            'retry_at':self.retry_at.isoformat() if self.retry_at else None,'quota':self.quota,
            'update_mode':'manual request; no automatic polling or streaming',
            'live_research_verified':False,'limits':['No evaluated model','Book rules and account availability unknown','No clock/possession game-state feed','Historical retrieval unavailable in this adapter']}
    def request(self,path,params=None):
        with self.lock:
            if not self.key: raise ProviderError('The Odds API key is not configured on the server')
            if self.retry_at and datetime.now(timezone.utc)<self.retry_at: raise ProviderError('Provider cooldown active; retry after reported time')
            if not re.fullmatch(r'/v4/sports(?:/[A-Za-z0-9_/-]+)?',path): raise ValueError('Invalid provider route')
            query=dict(params or {},apiKey=self.key)
            url='https://api.the-odds-api.com'+path+'?'+urllib.parse.urlencode(query)
            try:
                if self.transport:
                    payload,headers=self.transport(path,params or {})
                else:
                    req=urllib.request.Request(url,headers={'Accept':'application/json','User-Agent':'SportsResearchDesk/2'})
                    opener=urllib.request.build_opener(NoRedirect)
                    with opener.open(req,timeout=15) as response:
                        raw=response.read(8_000_001)
                        if len(raw)>8_000_000: raise ProviderError('Provider response exceeds supported size')
                        payload=json.loads(raw);headers=dict(response.headers)
                self.quota={k:str(v)[:40] for k,v in headers.items() if k.lower() in ['x-requests-remaining','x-requests-used','x-requests-last']}
                self.last_result='response_received'; self.retry_at=None
                return payload
            except urllib.error.HTTPError as exc:
                code=exc.code
                if code==429 or 500<=code<600:
                    self.retry_at=datetime.now(timezone.utc)+timedelta(seconds=60)
                self.last_result='rate_limited' if code==429 else 'http_'+str(code)
                raise ProviderError('Provider request rejected (HTTP '+str(code)+'); response body withheld') from None
            except (urllib.error.URLError,TimeoutError,OSError,json.JSONDecodeError):
                self.retry_at=datetime.now(timezone.utc)+timedelta(seconds=5)
                self.last_result='connection_or_schema_error'
                raise ProviderError('Provider connection or JSON response failed; raw diagnostics withheld') from None
    def sports(self):
        rows=self.request('/v4/sports',{'all':'true'})
        if not isinstance(rows,list): raise ProviderError('Invalid sport catalog')
        for row in rows:
            required(row,['key','title','group','active','has_outrights']); identifier(row['key'])
            if type(row['active']) is not bool or type(row['has_outrights']) is not bool: raise ProviderError('Invalid sport catalog flags')
        return [{k:r[k] for k in ['key','title','group','active','has_outrights']} for r in rows]
    def events(self,sport):
        rows=self.request('/v4/sports/'+identifier(sport)+'/events',{})
        if not isinstance(rows,list): raise ProviderError('Invalid event catalog')
        for row in rows:
            required(row,['id','sport_key','commence_time']); identifier(row['id']); timestamp(row['commence_time'])
            if row['sport_key']!=sport: raise ProviderError('Provider sport response mismatch')
        return rows
    def markets(self,sport,event,regions='us'):
        row=self.request('/v4/sports/'+identifier(sport)+'/events/'+identifier(event)+'/markets',{'regions':self.regions(regions)})
        if not isinstance(row,dict) or row.get('sport_key')!=sport or row.get('id')!=event: raise ProviderError('Provider event response mismatch')
        required(row,['bookmakers'])
        if not isinstance(row['bookmakers'],list): raise ProviderError('Invalid market discovery')
        for book in row['bookmakers']:
            required(book,['key','markets']); identifier(book['key'])
            if not isinstance(book['markets'],list): raise ProviderError('Invalid market discovery')
            for market in book['markets']: identifier(market['key'])
        return row
    def odds(self,sport,markets,regions='us',event=None):
        if not isinstance(markets,list) or not markets or len(markets)>40: raise ValueError('Select 1–40 exact market keys')
        keys=[identifier(k) for k in markets]
        if event is None and any(k not in ['h2h','spreads','totals','outrights'] for k in keys): raise ValueError('Additional markets require an exact event ID')
        path='/v4/sports/'+identifier(sport)+('/events/'+identifier(event) if event else '')+'/odds'
        payload=self.request(path,{'regions':self.regions(regions),'markets':','.join(keys),'oddsFormat':'decimal','dateFormat':'iso'})
        rows=[payload] if isinstance(payload,dict) else payload
        if not isinstance(rows,list) or any(not isinstance(r,dict) or r.get('sport_key')!=sport or event and r.get('id')!=event for r in rows): raise ProviderError('Provider odds response mismatch')
        if event and len(rows)!=1: raise ProviderError('Provider event response missing')
        result=normalize_odds(payload,now())
        if result['skipped']: self.last_result='response_with_unsupported_markets'
        else: self.last_result='schema_valid_observations'
        return result
    @staticmethod
    def regions(value):
        if not isinstance(value,str) or not value.split(',') or any(x not in ['us','us2','uk','au','eu','fr','se'] for x in value.split(',')): raise ValueError('Invalid regions')
        return value


class ProviderService:
    def __init__(self,store,adapter=None):
        self.store=store; self.adapters={'the_odds_api':adapter or OddsAPI()}; self.scan_lock=threading.RLock()
    def health(self): return [a.health() for a in self.adapters.values()]
    def catalog(self,user): return self.store.rows(user,'sports')
    def coverage(self,user):
        from engine import coverage
        catalog=[dict(s,status='catalog_only',live_research_verified=False,limitations=['Catalog membership is not verified bookmaker, market or operational coverage']) for s in self.catalog(user)]
        return coverage()+catalog+self.store.rows(user,'provider_discovery')+self.store.rows(user,'provider_coverage')
    def scan(self,user,data,adapter):
        """Breadth-first, resumable discovery. Every network call consumes request budget.

        This budget is not a credit cap: odds endpoint credits depend on markets/regions.
        A finite cycle samples all current events and recently seen market keys; it does
        not establish an exhaustive catalog or support for parlay joint probabilities.
        """
        budget=data.get('max_requests',5)
        if type(budget) is not int or not 1<=budget<=20: raise ValueError('Request budget must be 1–20')
        regions=adapter.regions(data.get('regions','us')); job_id=adapter.provider_id+':'+regions
        with self.scan_lock:
            existing=self.store.rows(user,'scan_jobs')
            job=next((r for r in existing if r['id']==job_id),None)
            queue=job['queue'] if job else []; calls=0; imported=0; done=[]; failures=[]; reset=False
            if job and (datetime.now(timezone.utc)-timestamp(job['created_at'])).total_seconds()>86400:
                queue=[];reset=True
            if not queue:
                catalog=[s for s in adapter.sports() if s['active']];calls+=1
                for row in catalog: self.store.put(user,'sports',row['key'],dict(row,provider=adapter.provider_id,retrieved_at=now()),replace=True)
                queue=[dict(action='odds',sport=s['key'],markets=['outrights'] if s['has_outrights'] else ['h2h','spreads','totals']) for s in catalog]
                queue += [dict(action='events',sport=s['key']) for s in catalog if not s['has_outrights']]
                job={'id':job_id,'created_at':now()}
            while queue and calls<budget:
                task=dict(queue[0]); calls+=1
                try:
                    if task['action']=='events':
                        events=adapter.events(task['sport'])
                        queue.extend(dict(action='markets',sport=task['sport'],event_id=e['id']) for e in events)
                    elif task['action']=='markets':
                        discovery=adapter.markets(task['sport'],task['event_id'],regions)
                        keys=set()
                        for book in discovery['bookmakers']:
                            for m in book['markets']:
                                key=m['key'];keys.add(key)
                                dims={'provider':adapter.provider_id,'league':task['sport'],'sportsbook':book['key'],'market_key':key}
                                self.store.put(user,'provider_discovery',digest(dims),dict(dims,status='recently_seen_key',retrieved_at=now(),live_research_verified=False,limitations=['Recently seen key only; price, rules, availability and model not verified']),replace=True)
                        keys=sorted(keys)
                        for offset in range(0,len(keys),40): queue.append(dict(action='odds',sport=task['sport'],event_id=task['event_id'],markets=keys[offset:offset+40]))
                    else:
                        result=self.action(user,dict(task,provider=adapter.provider_id,regions=regions))
                        imported+=result['imported']
                    done.append(task);queue.pop(0)
                except (ValueError,KeyError,TypeError) as exc:
                    failures.append(dict(task,reason=str(exc)))
                    attempts=task.get('attempts',0)+1
                    queue.pop(0)
                    if attempts<3: queue.append(dict(task,attempts=attempts))
                    else: self.store.put(user,'provider_failures',digest([job_id,task]),dict(task,attempts=attempts,reason=str(exc),failed_at=now()),replace=True)
                    if adapter.retry_at: break
                if len(queue)>50000: raise ProviderError('Discovery queue exceeds local capacity; use targeted retrieval')
                self.store.put(user,'scan_jobs',job_id,dict(job,queue=queue,updated_at=now()),replace=True)
            self.store.put(user,'scan_jobs',job_id,dict(job,queue=queue,updated_at=now()),replace=True)
            return {'imported':imported,'provider_requests':calls,'completed_tasks':done,'failures':failures,'pending_tasks':len(queue),'cycle_complete':not queue,'expired_cycle_reset':reset,
                'limitation':'Resumable discovery of all active leagues, featured/outright prices, current events and all recently seen event-market keys in selected regions. This is not exhaustive supported or operational coverage. No parlay probability, lay liability, evaluated model, verified rules or game-state feed.',
                'cost_note':'Request count is not a credit cap. Odds credits depend on returned markets and regions; all event-market keys may have substantial cost. Manual invocation only.'}
    def action(self,user,data):
        adapter=self.adapters.get(data.get('provider'))
        try: return self._action(user,data)
        except (ValueError,KeyError,TypeError) as exc:
            if adapter and not isinstance(exc,ProviderError):
                adapter.last_result='schema_or_identity_rejected'
            raise
        finally:
            if adapter: self.store.put(user,'provider_health',adapter.provider_id,adapter.health(),replace=True)

    def _action(self,user,data):
        required(data,['provider','action'])
        adapter=self.adapters.get(data['provider'])
        if not adapter: raise ValueError('Unsupported provider')
        action=data['action']
        if action=='sports':
            rows=adapter.sports()
            for row in rows: self.store.put(user,'sports',row['key'],dict(row,provider=adapter.provider_id,retrieved_at=now()),replace=True)
            return {'sports':rows,'cost_note':'Sport catalog endpoint does not consume provider usage credits'}
        if action=='events': return {'events':adapter.events(data['sport'])}
        if action=='markets': return {'markets':adapter.markets(data['sport'],data['event_id'],data.get('regions','us')),'cost_note':'Recently seen keys only; not exhaustive supported coverage; provider credits apply'}
        if action=='odds':
            result=adapter.odds(data['sport'],data['markets'],data.get('regions','us'),data.get('event_id'))
        elif action=='scan_all': return self.scan(user,data,adapter)
        elif action=='import_snapshot':
            required(data,['payload','retrieved_at'])
            result=normalize_odds(data['payload'],data['retrieved_at'],'manual_unverified')
        else: raise ValueError('Unsupported provider action')
        # Each quote has a deterministic identifier; retries cannot overwrite histories.
        saved=self.store.bulk_quotes(user,result['quotes'])
        for q in result['quotes']:
            dims={k:q[k] for k in ['sport','league','sportsbook','market','market_key','scope']}
            row=dict(dims,provider=adapter.provider_id,observed_at=q['observed_at'],retrieved_at=q['retrieved_at'],
                source_observed=action=='odds' and adapter.transport is None,live_research_verified=False,
                status='source_observed' if action=='odds' and adapter.transport is None else 'imported_unverified',
                limitations=['Settlement rules unknown','Account price availability unknown','No evaluated model','Live odds lack aligned state' if q['scope']=='live' else 'Historical coverage unverified'])
            self.store.put(user,'provider_coverage',digest(dims),row,replace=True)
        return {'imported':sum(not r['duplicate'] for r in saved),'duplicates':sum(r['duplicate'] for r in saved),
            'skipped':result['skipped'],'qualification':'unevaluable; no validated model or verified rules/availability'}
