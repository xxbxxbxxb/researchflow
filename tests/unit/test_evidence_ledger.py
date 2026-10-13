import importlib
from dataclasses import replace
from datetime import UTC, datetime
from hashlib import sha256

import pytest
from researchflow.domain.research import Evidence


def api():
    if importlib.util.find_spec('researchflow.application.evidence') is None:
        pytest.fail('Anchored evidence and atomic ledger are not implemented')
    return importlib.import_module('researchflow.application.evidence'), importlib.import_module('researchflow.domain.sources')


def material():
    app, types = api()
    page = types.SnapshotPage(1, '样本量是12。\r\n第二句。')
    snapshot = types.SourceSnapshot('snapshot-a', 'project-a', 'manual:paper', sha256(b'raw').hexdigest(), (page,), 'text-v1', datetime.now(UTC))
    item = app.anchor_evidence(snapshot, 1, 0, 8)
    return app, snapshot, item


def test_snapshot_normalizes_page_text_and_anchor_is_exact():
    app, snapshot, item = material()
    assert snapshot.pages[0].text == '样本量是12。\n第二句。'
    assert item.evidence.text == '样本量是12。\n'
    app.validate_anchor(item, snapshot)


def test_corrupted_offset_and_hash_are_rejected():
    app, snapshot, item = material()
    for bad in [replace(item, anchor=replace(item.anchor, start=1)), replace(item, quote_hash='bad')]:
        with pytest.raises(ValueError):
            app.validate_anchor(bad, snapshot)


def test_same_identity_same_content_is_idempotent():
    app, snapshot, item = material()
    ledger = app.EvidenceLedger((snapshot,))
    assert ledger.add_batch('project-a', (item,)) == (item,)
    assert ledger.add_batch('project-a', (item,)) == (item,)
    assert ledger.get('project-a', item.evidence.evidence_id) == item


def test_conflict_rolls_back_entire_batch():
    app, snapshot, item = material()
    ledger = app.EvidenceLedger((snapshot,))
    ledger.add_batch('project-a', (item,))
    fresh = app.anchor_evidence(snapshot, 1, 8, 12)
    changed = replace(item, extractor_version='other')
    with pytest.raises(ValueError):
        ledger.add_batch('project-a', (fresh, changed))
    assert ledger.get('project-a', fresh.evidence.evidence_id) is None


def test_cross_project_source_cannot_be_referenced():
    app, snapshot, item = material()
    ledger = app.EvidenceLedger((snapshot,))
    with pytest.raises(ValueError):
        ledger.add_batch('project-b', (item,))
    assert ledger.get('project-b', item.evidence.evidence_id) is None


def test_duplicate_conflict_within_batch_is_rejected():
    app, snapshot, item = material()
    ledger = app.EvidenceLedger((snapshot,))
    with pytest.raises(ValueError):
        ledger.add_batch('project-a', (item, replace(item, extractor_version='other')))
    assert ledger.get('project-a', item.evidence.evidence_id) is None


def test_manual_source_retains_legacy_provenance():
    app, _ = api()
    snapshot, anchored = app.manual_evidence('project-a', Evidence('t:E001', 'User supplied paper', 'p.2', 'The sample was 12.'))
    assert anchored.evidence.evidence_id == 't:E001'
    assert anchored.evidence.source == 'User supplied paper'
    assert anchored.evidence.locator == 'p.2'
    assert snapshot.source_uri.startswith('manual:')
    app.validate_anchor(anchored, snapshot)
