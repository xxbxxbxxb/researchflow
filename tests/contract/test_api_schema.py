def test_openapi_exposes_typed_report_and_evidence_contracts_for_web_generation():
    from researchflow.api.app import create_app
    from researchflow.settings import Settings
    schema = create_app(Settings(database_url='postgresql+psycopg://unused/unused')).openapi()
    response = schema['paths']['/api/reports/{report_id}']['get']['responses']['200']['content']['application/json']['schema']
    assert response.get('$ref','').endswith('/ResearchResult'), 'Web must consume the actual typed report bundle'
    assert 'EvidenceAnchor' in schema['components']['schemas']
