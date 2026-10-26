"""The development API has no bearer-token authentication dependency."""
from app.main import app
from app.api import analytics
from app.schemas.analytics import AnalyticsRequest


def test_openapi_has_no_bearer_security_scheme():
    spec = app.openapi()
    assert 'HTTPBearer' not in spec.get('components', {}).get('securitySchemes', {})
    for path in ('/analytics/run', '/analytics/report/pdf', '/analytics/runs/{analysis_id}'):
        assert not spec['paths'][path][next(iter(spec['paths'][path]))].get('security')


def test_analytics_request_uses_selected_tables_without_credentials(monkeypatch):
    seen = {}

    def fake_execute(request, engine, initial):
        seen['tables'] = initial['selected_tables']
        return {'approval_status': 'pending', 'analysis_plan': 'Review the proposed analysis.'}

    monkeypatch.setattr('app.workflow.recovery.execute', fake_execute)
    monkeypatch.setattr('app.audit.service.record_audit_event', lambda **kwargs: None)
    result = analytics.run_analytics(AnalyticsRequest(
        question='Count subjects by treatment arm', selected_tables=['adsl', 'dm'],
    ))
    assert result.status == 'awaiting_approval'
    assert seen['tables'] == ['adsl', 'dm']
