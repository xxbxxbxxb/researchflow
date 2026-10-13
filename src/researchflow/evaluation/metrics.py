from researchflow.evaluation.dataset import Metrics


def compute_metrics(predictions):
    labels=('supported','contradicted','insufficient')
    outcomes=(*labels,'inconclusive','failed')
    matrix={gold:{predicted:0 for predicted in outcomes} for gold in labels}
    if len({p.case_id for p in predictions})!=len(predictions):
        raise ValueError('duplicate evaluation prediction')
    for p in predictions:
        if p.gold not in labels or p.predicted not in outcomes:
            raise ValueError('invalid evaluation label')
        if not set(p.accepted_evidence_ids)<=set(p.provided_evidence_ids):
            raise ValueError('evaluation prediction fabricated a citation')
        matrix[p.gold][p.predicted]+=1
    tp=matrix['supported']['supported']
    predicted_support=sum(matrix[g]['supported'] for g in labels)
    gold_support=sum(matrix['supported'].values())
    accepted=sum(len(set(p.accepted_evidence_ids)) for p in predictions)
    provided=sum(len(set(p.provided_evidence_ids)) for p in predictions)
    total=len(predictions)
    completed=sum(p.predicted in labels for p in predictions)
    correct=sum(matrix[g][g] for g in labels)
    return Metrics(total,completed,tp/predicted_support if predicted_support else None,tp/gold_support if gold_support else None,correct/total if total else None,accepted/provided if provided else None,matrix,tuple(p.case_id for p in predictions if p.predicted=='supported' and p.gold!='supported'))
