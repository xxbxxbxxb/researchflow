"""Select immutable original SciFact claim/document groups, without model-created gold."""
import argparse
import hashlib
import json
import re
import tarfile
from pathlib import Path
from typing import Any

URL='https://scifact.s3-us-west-2.amazonaws.com/release/latest/data.tar.gz'
EXPECTED_HASH='11c621288d41ac144d29b13b0f8503b3820b7d6e8b1f6ff24dff335c196d76be'


def prepare(archive: Path,output: Path):
    raw=archive.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=EXPECTED_HASH:
        raise ValueError('original SciFact archive differs from the frozen source')
    with tarfile.open(archive) as tar:
        def read(name):
            member=tar.getmember('data/'+name)
            if member.size>30*1024*1024 or not member.isfile():
                raise ValueError('invalid dataset archive member')
            return [(json.loads(line),hashlib.sha256(line).hexdigest()) for line in tar.extractfile(member) if line.strip()]
        corpus={row['doc_id']:(row,digest) for row,digest in read('corpus.jsonl')}
        source={'train':read('claims_train.jsonl'),'dev':read('claims_dev.jsonl')}
    used_claims=set()
    used_docs=set()
    groups={}
    for split,origin in [('development','train'),('holdout','dev')]:
        buckets: dict[str,list[dict[str,Any]]]={'supported':[],'contradicted':[],'insufficient':[]}
        for claim,digest in source[origin]:
            if claim['evidence']:
                doc_id=sorted(claim['evidence'],key=int)[0]
                annotation=claim['evidence'][doc_id]
                label=annotation[0]['label']
                gold={'SUPPORT':'supported','CONTRADICT':'contradicted'}[label]
                if any(a['label']!=label for a in annotation):
                    continue
                sentences=sorted({i for a in annotation for i in a['sentences']})
                doc_id=int(doc_id)
            else:
                gold='insufficient'
                if not claim['cited_doc_ids']:
                    continue
                doc_id=claim['cited_doc_ids'][0]
                sentences=[]
            if doc_id not in corpus or claim['id'] in used_claims or doc_id in used_docs:
                continue
            document,doc_hash=corpus[doc_id]
            tags=[]
            if re.search(r'\d',claim['claim']):
                tags.append('numeric_claim')
                if gold=='contradicted':
                    tags.append('numeric_contradiction')
            if re.search(r'\b(in|without|only|not|human|cells|mice|mouse|patient|inhibit|increase|decrease)\b',claim['claim'],re.I):
                tags.append('condition_or_population')
                if gold=='contradicted':
                    tags.append('condition_contradiction')
            buckets[gold].append({'case_id':f"scifact-{claim['id']}-{doc_id}",'claim_id':claim['id'],'doc_id':doc_id,'claim':claim['claim'],'abstract':document['abstract'],'title':document['title'],'gold':gold,'evidence_sentences':sentences,'source_split':origin,'source_hash':digest,'document_hash':doc_hash,'tags':tags})
        selected=[]
        for gold,rows in buckets.items():
            rows.sort(key=lambda row:(-len(row['tags']),row['claim_id']))
            count=0
            for row in rows:
                if row['doc_id'] in used_docs or row['claim_id'] in used_claims:
                    continue
                selected.append(row)
                used_docs.add(row['doc_id'])
                used_claims.add(row['claim_id'])
                count+=1
                if count==4:
                    break
            if count!=4:
                raise ValueError('not enough independent original labels for a balanced split')
        groups[split]=selected
    output.mkdir(parents=True,exist_ok=True)
    manifest: dict[str,Any]={'source_url':URL,'archive_sha256':EXPECTED_HASH,'claim_license':'CC BY 4.0','abstract_license':'ODC-By 1.0','citation':'Wadden et al. (2020), Fact or Fiction: Verifying Scientific Claims, EMNLP 2020. https://aclanthology.org/2020.emnlp-main.609/','selection':'original train/dev labels; grouped by claim and document; full abstract given to verifier, gold rationale kept only for auditing','splits':{}}
    for split,rows in groups.items():
        data=('\n'.join(json.dumps(row,ensure_ascii=False,sort_keys=True) for row in rows)+'\n').encode()
        (output/(split+'.jsonl')).write_bytes(data)
        manifest['splits'][split]={'size':len(rows),'sha256':hashlib.sha256(data).hexdigest(),'claim_ids':[r['claim_id'] for r in rows],'doc_ids':[r['doc_id'] for r in rows]}
    (output/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('archive',type=Path)
    parser.add_argument('--output',type=Path,default=Path(__file__).parent/'data')
    args=parser.parse_args()
    prepare(args.archive,args.output)
