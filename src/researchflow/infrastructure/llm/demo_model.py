import json

from researchflow.ports.model import ChatRequest, ChatResponse

CASES = {
    'supported': {'question':'合成研究的样本量是多少？','source':'The synthetic study used a sample size of 12, only for Chinese text.','claim':'The synthetic study used a sample size of 12, only for Chinese text.','status':'supported'},
    'contradicted': {'question':'样本量为12的说法是否受到材料支持？','source':'The synthetic study used a sample size of 24.','claim':'The synthetic study used a sample size of 12.','status':'contradicted'},
    'insufficient': {'question':'缺少资料时能否回答？','source':'','claim':'','status':'insufficient'},
    'invalid-citation': {'question':'演示非法引用被阻止。','source':'The sample size was 12.','claim':'The sample size was 12.','status':'supported'},
}


class DemoCaseModel:
    """Explicit fixed-output fixture. This class is never a live fallback."""
    def __init__(self, case: str = 'supported') -> None:
        if case not in CASES:
            raise ValueError('unknown fixed demonstration case')
        self.case = case

    async def complete(self, request: ChatRequest) -> ChatResponse:
        data = json.loads(request.messages[1].content)
        fixture = CASES[self.case]
        if request.operation == 'claims':
            refs = ['missing'] if self.case == 'invalid-citation' else [e['evidence_id'] for e in data['evidence']]
            payload = {'claims':[{'text':fixture['claim'],'evidence_ids':refs,'qualifiers':[]}]} if fixture['claim'] else {'claims':[]}
        elif request.operation == 'verify':
            refs = [e['evidence_id'] for e in data['evidence']]
            quotes = [{'evidence_id':e['evidence_id'],'quote':e['text']} for e in data['evidence']]
            payload = {'verifications':[{'claim_id':c['claim_id'],'status':fixture['status'],'evidence_ids':refs,'quotes':quotes,'rationale':'固定演示标签，非真实模型评测。'} for c in data['claims']]}
        else:
            raise ValueError('fixed fixture does not implement this operation')
        return ChatResponse(json.dumps(payload,ensure_ascii=False),model='demo:fixed-case-v1')
