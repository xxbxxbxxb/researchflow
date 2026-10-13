def execution_metrics(events,usage):
    """Derive observations from durable facts; no second business database."""
    phases=[]
    start=None
    from datetime import datetime
    for event in events:
        timestamp=datetime.fromisoformat(event['created_at'])
        if event['kind'] in ('claimed','recovered'):
            start=timestamp
        elif event['kind']=='step_committed':
            phases.append({'step_id':event['data']['step_key'],'elapsed_since_previous_seconds':max(0,(timestamp-start).total_seconds()) if start else None})
            start=timestamp
    known=bool(usage) and all(u['input_tokens'] is not None and u['output_tokens'] is not None for u in usage)
    cost=sum(u['estimated_cost'] for u in usage) if usage and all(u['estimated_cost'] is not None for u in usage) else None
    return {'phases':phases,'model_attempts':len(usage),'retries':sum(u['status']=='provider_failure' for u in usage),'recoveries':sum(e['kind']=='recovered' for e in events),'usage_known':known,'estimated_cost':cost}
