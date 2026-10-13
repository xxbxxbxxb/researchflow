import importlib
from dataclasses import replace
from datetime import datetime, timezone

import pytest

from researchflow.domain.sources import SnapshotPage, SourceSnapshot


def test_chunks_keep_offsets_and_selection_removes_overlapping_ranges():
    try:
        m = importlib.import_module('researchflow.application.retrieval')
        types = importlib.import_module('researchflow.ports.retrieval')
    except ModuleNotFoundError:
        pytest.fail('retrieval selection not implemented')
    snapshot = SourceSnapshot('s','p','upload:paper','hash',(SnapshotPage(1,'中文' * 1000),),'test',datetime.now(timezone.utc))
    chunks = m.chunk_snapshot(snapshot)
    assert [(c.start,c.end) for c in chunks] == [(0,800),(700,1500),(1400,2000)]
    assert all(snapshot.pages[0].text[c.start:c.end] == c.text for c in chunks)
    result = types.RetrievalResult((*chunks, replace(chunks[0], chunk_id='duplicate')),'lexical',None)
    evidence = m.EvidenceSelector().select(result)
    assert len(evidence) == 3
    assert m.EvidenceSelector().select(types.RetrievalResult((),'lexical',None)) == ()
