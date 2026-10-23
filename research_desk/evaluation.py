"""Audit historical binary predictions; no training or model promotion.
Rows must represent the complete selection universe, not only chosen winners.
This cannot independently verify provenance or absence of omitted records.
"""
import math
from engine import timestamp, number

def evaluate(rows,train_end,validation_end):
    if not isinstance(rows,list) or len(rows)>100000 or any(not isinstance(r,dict) for r in rows): raise ValueError('Expected at most 100000 prediction objects')
    train_end=timestamp(train_end); validation_end=timestamp(validation_end)
    if train_end>=validation_end: raise ValueError('Chronological boundaries invalid')
    partitions={'train':[],'validation':[],'test':[]}
    identifiers=set()
    event_partitions={}
    for original in rows:
        row=dict(original)
        for key in ['id','event_id','sport','market']:
            if not isinstance(row.get(key),str) or not row[key].strip(): raise ValueError('Missing prediction text: '+key)
        if row['id'] in identifiers: raise ValueError('Duplicate prediction')
        identifiers.add(row['id'])
        t=timestamp(row['prediction_at'])
        for k in ['inputs_available_at','odds_observed_at']:
            if timestamp(row[k])>t: raise ValueError('Future information: '+k)
        if timestamp(row['result_available_at'])<=t: raise ValueError('Result already available at prediction')
        if type(row['outcome']) is not int or row['outcome'] not in [0,1] or row.get('settlement_type')!='binary': raise ValueError('Only binary full-win/loss evaluation supported')
        for k in ['probability','baseline_probability']:
            row[k]=number(row[k])
            if not 0<=row[k]<=1: raise ValueError('Invalid probability')
        row['decimal_odds']=number(row['decimal_odds'],1)
        if row['decimal_odds']<=1: raise ValueError('Invalid odds')
        for k in ['selected','executable']:
            if k in row and type(row[k]) is not bool: raise ValueError(k+' must be boolean')
        if row.get('selected') and row.get('executable'):
            if timestamp(row['execution_at'])<t or timestamp(row['price_available_until'])<timestamp(row['execution_at']): raise ValueError('Execution price unavailable')
            if timestamp(row['execution_at'])>=timestamp(row['result_available_at']): raise ValueError('Execution after result')
            row['execution_decimal_odds']=number(row['execution_decimal_odds'],1)
            if row['execution_decimal_odds']<=1: raise ValueError('Invalid execution price')
            observed=timestamp(row['execution_odds_observed_at']); executed_at=timestamp(row['execution_at'])
            max_age=number(row.get('max_execution_quote_age_seconds',300))
            if observed>executed_at or (executed_at-observed).total_seconds()>max_age: raise ValueError('Stale or future execution odds')
            row['stake']=number(row['stake']); row['fees']=number(row['fees'])
            if row['stake']<=0: raise ValueError('Execution requires positive stake')
        partition='train' if t<=train_end else 'validation' if t<=validation_end else 'test'
        cutoff={'train':train_end,'validation':validation_end}.get(partition)
        if cutoff and timestamp(row['result_available_at'])>cutoff: raise ValueError('Label unavailable at partition fitting/selection cutoff')
        for key in ['model_fitted_at','preprocessing_fitted_at','calibration_fitted_at']:
            if row.get(key) and timestamp(row[key])>t: raise ValueError('Future fitted artifact: '+key)
        if partition=='test' and row.get('model_selected_at') and timestamp(row['model_selected_at'])>validation_end: raise ValueError('Test data used in model selection')
        event=row['event_id']
        if event in event_partitions and event_partitions[event]!=partition: raise ValueError('Event spans chronological partitions')
        event_partitions[event]=partition
        partitions[partition].append(row)
    def metrics(rs):
        n=len(rs)
        if not n: return {'n':0}
        out={'n':n}
        for key in ['probability','baseline_probability']:
            brier=sum((r[key]-r['outcome'])**2 for r in rs)/n
            loss=-sum(r['outcome']*math.log(max(1e-15,r[key]))+(1-r['outcome'])*math.log(max(1e-15,1-r[key])) for r in rs)/n
            out[key]={'brier':brier,'log_loss':loss,'calibration':[]}
            for i in range(10):
                binrows=[r for r in rs if i/10<=r[key]<(i+1)/10 or i==9 and r[key]==1]
                if binrows: out[key]['calibration'].append({'bin':i,'n':len(binrows),'mean_prediction':sum(r[key] for r in binrows)/len(binrows),'observed_frequency':sum(r['outcome'] for r in binrows)/len(binrows)})
        executed=[r for r in rs if r.get('selected') and r.get('executable')]
        profit=sum(r['stake']*(r['execution_decimal_odds']-1 if r['outcome'] else -1)-r['fees'] for r in executed)
        stake=sum(r['stake'] for r in executed)
        out.update(executed_n=len(executed),selected_n=sum(bool(r.get('selected')) for r in rs),stake=stake,profit=profit,roi=profit/stake if stake else None)
        return out
    result={k:metrics(v) for k,v in partitions.items()}
    result['held_out_breakdowns']={}
    groups={}
    for row in partitions['test']:
        key=(row['sport'],row['market'],str(row['season']))
        groups.setdefault(key,[]).append(row)
    for key,group in groups.items(): result['held_out_breakdowns'][' / '.join(key)]=metrics(group)
    result['conclusion']='Descriptive audit only. No model promotion; no proof of profitability or selection-universe completeness. Uncertainty intervals unavailable.'
    return result

def closing_line_value(wager,closing):
    fields=['sport','league','event_id','market','market_key','participant_id','selection','line','period','rules','sportsbook']
    if any(wager.get(k)!=closing.get(k) for k in fields): raise ValueError('Closing wager not equivalent')
    if timestamp(closing['observed_at'])<timestamp(wager['placed_at']) or timestamp(closing['observed_at'])>timestamp(closing['start_at']): raise ValueError('Invalid closing observation time')
    if not closing.get('source_ref'): raise ValueError('Closing source missing')
    d=number(wager['decimal_odds'],1); c=number(closing['decimal_odds'],1)
    if min(d,c)<=1: raise ValueError('Invalid odds')
    return {'price_ratio_minus_one':d/c-1,'source':closing['source_ref'],'observed_at':closing['observed_at'],'method':'placed decimal / exact-wager closing decimal - 1; no changed-line conversion; observed close not independently verified'}
