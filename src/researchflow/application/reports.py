import re
from datetime import UTC, datetime
from urllib.parse import quote
from uuid import uuid4

from researchflow.domain.reports import ReportInputs, ReportVersion


def markdown_text(text: str) -> str:
    return re.sub(r'([\\`*_{}\[\]<>])', r'\\\1', text)


class ReportBuilder:
    def build(self, result_inputs: ReportInputs) -> ReportVersion:
        data = result_inputs
        claims = {c.claim_id:c for c in data.claims}
        verdicts = {v.claim_id:v for v in data.verifications}
        evidence = {e.evidence.evidence_id:e for e in data.evidences}
        if len(claims) != len(data.claims) or len(verdicts) != len(data.verifications) or set(claims) != set(verdicts):
            raise ValueError('every report claim needs exactly one verification')
        if any(c.project_id != data.project_id or c.task_id != data.task_id for c in data.claims) or any(e.project_id != data.project_id for e in data.evidences):
            raise ValueError('report crosses project or task scope')
        if any(ref not in evidence for v in data.verifications for ref in v.accepted_evidence_ids):
            raise ValueError('report cites unavailable evidence')
        supported = tuple(c.claim_id for c in data.claims if verdicts[c.claim_id].status == 'supported')
        other = tuple(c.claim_id for c in data.claims if verdicts[c.claim_id].status != 'supported')
        used = tuple(dict.fromkeys(ref for v in data.verifications for ref in v.accepted_evidence_ids))
        aliases = {eid:f'E{i+1}' for i,eid in enumerate(used)}
        lines = ['# 研究报告', '', markdown_text(data.question), '', '## 有依据的结论', '']
        if data.execution_mode == 'demo':
            lines[1:1] = ['','> 固定演示案例：验证流程与交互，不代表真实模型质量。','']
        if not supported:
            lines += ['证据不足：当前材料没有形成可确认支持的结论。','']
        for cid in supported:
            c,v = claims[cid],verdicts[cid]
            citations = ' '.join(f'[{aliases[eid]}](/api/evidence/{quote(eid,safe="")})' for eid in v.accepted_evidence_ids)
            lines += [f'- {markdown_text(c.text)} {citations}']
        lines += ['','## 相反证据与待核实事项','']
        labels = {'contradicted':'相反证据','insufficient':'材料不足','inconclusive':'验证受限'}
        for cid in other:
            c,v = claims[cid],verdicts[cid]
            lines += [f'- **{labels[v.status]}**：{markdown_text(c.text)} — {markdown_text(v.rationale)}']
        lines += ['','## 后续问题',''] + [f'- {markdown_text(q)}' for q in data.unresolved_questions]
        lines += ['','## 参考来源','']
        for eid in used:
            item = evidence[eid]
            lines += [f'- [{aliases[eid]}](/api/evidence/{quote(eid,safe="")}) {markdown_text(item.evidence.source)}，{markdown_text(item.evidence.locator)}']
        return ReportVersion(uuid4().hex,data.project_id,data.task_id,data.run_id,1,'\n'.join(lines),supported,other,used,data.execution_mode,datetime.now(UTC),data.retrieval_mode)
