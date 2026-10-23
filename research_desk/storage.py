"""Indexed quote read model and explicit identity changes; no fuzzy event matching."""
import json

class IndexedQuotes:
    def fingerprint(self,q):
        from engine import digest
        # Retrieval and envelope hashes change on retry; economic content does not.
        value={k:v for k,v in q.items() if k not in {'id','snapshot_id','retrieved_at','source_payload_hash','event','sportsbook_name','source_ref'}}
        if not q.get('observed_at'): value['retrieved_at']=q['retrieved_at']
        return digest(value)

    def index_quote(self,c,user,q):
        from engine import contract,quote_order,digest,book_id
        c.execute('INSERT OR IGNORE INTO quote_lookup(user,id,event_id,book,observed,contract_key,book_key) VALUES(?,?,?,?,?,?,?)',
                  (user,q['id'],q['event_id'],book_id(q['sportsbook']),quote_order(q).timestamp(),digest(contract(q)),digest(contract(q,True))))
        c.execute('INSERT OR IGNORE INTO snapshot_keys VALUES(?,?,?)',(user,self.fingerprint(q),q['id']))

    def initialize_indexes(self):
        with self.connect() as c:
            c.executescript('''
            CREATE TABLE IF NOT EXISTS quote_lookup(seq INTEGER PRIMARY KEY AUTOINCREMENT,user TEXT,id TEXT,event_id TEXT,book TEXT,observed REAL,contract_key TEXT,book_key TEXT,UNIQUE(user,id));
            CREATE INDEX IF NOT EXISTS quote_latest ON quote_lookup(user,book_key,observed DESC);
            CREATE INDEX IF NOT EXISTS quote_event_history ON quote_lookup(user,event_id,seq);
            CREATE INDEX IF NOT EXISTS quote_book_history ON quote_lookup(user,book,seq);
            CREATE INDEX IF NOT EXISTS quote_contract ON quote_lookup(user,contract_key,seq);
            CREATE INDEX IF NOT EXISTS quote_page ON quote_lookup(user,seq);
            CREATE TABLE IF NOT EXISTS snapshot_keys(user TEXT,fingerprint TEXT,id TEXT,PRIMARY KEY(user,fingerprint));
            CREATE TABLE IF NOT EXISTS schema_versions(version INTEGER PRIMARY KEY);
            ''')
            c.execute('BEGIN IMMEDIATE')
            if not c.execute('SELECT 1 FROM schema_versions WHERE version=1').fetchone():
                for row in c.execute("SELECT user,payload FROM records WHERE kind='quotes'").fetchall(): self.index_quote(c,row['user'],json.loads(row['payload']))
                c.execute('INSERT INTO schema_versions VALUES(1)')

    def resolve_identity(self,user,q):
        from engine import digest,book_id
        # Aliases require an explicit, league-scoped operator decision; never fuzzy merge.
        for a in self.rows(user,'aliases'):
            if a['league']!=q['league']: continue
            fields=['sportsbook'] if a['kind']=='book' else ['selection','participant_id']
            for field in fields:
                if isinstance(q.get(field),str) and book_id(q[field])==book_id(a['source']): q[field]=a['target']
        key=digest([q['provider'],q['league'],q['provider_event_id']])
        existing=next((m for m in self.rows(user,'event_maps') if m['id']==key),None)
        expected={k:q[k] for k in ['provider','provider_event_id','event_id','sport','league','start_at']}
        if existing:
            if any(existing[k]!=v for k,v in expected.items()) or existing['status']!='active':
                raise ValueError('Event mapping conflict: register an explicit reschedule/remap before import')
        else:
            # An upstream ID cannot silently join an existing canonical event.
            if any(m['event_id']==q['event_id'] and (m['provider'],m['provider_event_id'])!=(q['provider'],q['provider_event_id']) for m in self.rows(user,'event_maps')):
                raise ValueError('Canonical event already bound; explicit cross-provider mapping required')
            self.put(user,'event_maps',key,dict(expected,id=key,status='active',revision=1))
        return q

    def event_mapping(self,user,data):
        from engine import serialized
        return serialized(IndexedQuotes._event_mapping)(self,user,data)

    def _event_mapping(self,user,data):
        from engine import required,text_fields,timestamp,digest
        fields=['provider','provider_event_id','event_id','sport','league','start_at','status','revision','reason']
        required(data,fields);text_fields(data,[k for k in fields if k!='revision'])
        if data['status'] not in ['active','postponed','cancelled']: raise ValueError('Invalid event status')
        if type(data['revision']) is not int or data['revision']<1: raise ValueError('Invalid mapping revision')
        data={k:data[k] for k in fields};data['start_at']=timestamp(data['start_at']).isoformat()
        key=digest([data['provider'],data['league'],data['provider_event_id']]);data['id']=key
        old=next((m for m in self.rows(user,'event_maps') if m['id']==key),None)
        if old==data: return {'id':key,'duplicate':True}
        if old and data['revision']<=old['revision']: raise ValueError('Mapping revision must increase')
        return self.put(user,'event_maps',key,data,replace=True)

    def alias(self,user,data):
        from engine import serialized
        return serialized(IndexedQuotes._alias)(self,user,data)

    def _alias(self,user,data):
        from engine import required,text_fields,digest,book_id
        fields=['kind','league','source','target'];required(data,fields);text_fields(data,fields)
        if data['kind'] not in ['team','book']: raise ValueError('Invalid alias kind')
        data={k:data[k] for k in fields}
        key=digest([data['kind'],data['league'],book_id(data['source'])])
        return self.put(user,'aliases',key,data)  # Immutable; conflicting aliases fail closed.

    def save_quote(self,user,q):
        from engine import encoded
        with self.connect() as c:
            old=c.execute("SELECT payload FROM records WHERE user=? AND kind='quotes' AND id=?",(user,q['id'])).fetchone()
            if old and old[0]!=encoded(q): raise ValueError('Identifier conflict; existing record differs')
            prior=c.execute('SELECT id FROM snapshot_keys WHERE user=? AND fingerprint=?',(user,self.fingerprint(q))).fetchone()
            if prior: return {'id':prior[0],'duplicate':True}
            result=self.put(user,'quotes',q['id'],q)
            self.index_quote(c,user,q)
            return result

    def odds_page(self,user,latest=True,limit=100,offset=0,event_id=None,sportsbook=None,after=None,before=None):
        from engine import read_snapshot
        return read_snapshot(IndexedQuotes._odds_page)(self,user,latest,limit,offset,event_id,sportsbook,after,before)

    def _odds_page(self,user,latest,limit,offset,event_id,sportsbook,after,before):
        from engine import timestamp,book_id
        if type(limit) is not int or not 1<=limit<=500 or type(offset) is not int or not 0<=offset<=1000000: raise ValueError('Invalid pagination')
        clauses=['q.user=?'];args=[user]
        for col,value in [('event_id',event_id),('book',book_id(sportsbook) if sportsbook else None)]:
            if value is not None: clauses.append('q.'+col+'=?');args.append(value)
        for op,value in [('>=',after),('<=',before)]:
            if value is not None: clauses.append('q.observed'+op+'?');args.append(timestamp(value).timestamp())
        if latest: clauses.append('NOT EXISTS (SELECT 1 FROM quote_lookup newer WHERE newer.user=q.user AND newer.book_key=q.book_key AND newer.observed>q.observed)')
        sql="SELECT r.payload,q.contract_key FROM quote_lookup q JOIN records r ON r.user=q.user AND r.kind='quotes' AND r.id=q.id WHERE "+' AND '.join(clauses)+' ORDER BY q.seq LIMIT ? OFFSET ?'
        with self.connect() as c:
            found=c.execute(sql,args+[limit+1,offset]).fetchall();page=found[:limit]
            items=[json.loads(r[0]) for r in page]
            if latest and page:
                keys=list({r[1] for r in page})
                context=c.execute("SELECT r.payload FROM quote_lookup q JOIN records r ON r.user=q.user AND r.kind='quotes' AND r.id=q.id WHERE q.user=? AND q.contract_key IN ("+','.join('?' for _ in keys)+") AND NOT EXISTS (SELECT 1 FROM quote_lookup n WHERE n.user=q.user AND n.book_key=q.book_key AND n.observed>q.observed)",[user]+keys).fetchall()
                computed={r['id']:r for r in self.board(user,quote_rows=[json.loads(r[0]) for r in context])}
                items=[computed[r['id']] for r in items]
        return {'items':items,'next_offset':offset+limit if len(found)>limit else None}

    def record_page(self,user,kind,limit=100,offset=0):
        if not 1<=limit<=500 or not 0<=offset<=1000000: raise ValueError('Invalid pagination')
        with self.connect() as c:
            if kind=='audit': rows=[dict(r) for r in c.execute('SELECT * FROM audit WHERE user=? ORDER BY sequence LIMIT ? OFFSET ?',(user,limit+1,offset))]
            else: rows=[json.loads(r[0]) for r in c.execute('SELECT payload FROM records WHERE user=? AND kind=? ORDER BY rowid LIMIT ? OFFSET ?',(user,kind,limit+1,offset))]
        return {'items':rows[:limit],'next_offset':offset+limit if len(rows)>limit else None}
