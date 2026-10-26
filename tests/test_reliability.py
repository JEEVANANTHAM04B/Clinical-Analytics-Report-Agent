"""Failure-path tests use synthetic rows; they are not clinical evidence."""
import copy
import json
import time
from decimal import Decimal
import pytest
from app.analytics.result_validator import validate_results, result_contract
from app.analytics.eda import assess_results
from app.analytics.cache import ResultCache
from app.workflow.runtime import stage_wrapper
from app.visualization.validation import validate_chart
from app.reporting.validation import validate_pdf


@pytest.mark.parametrize("rows,code", [([], "EMPTY_RESULT"), ([1], "RESULT_STRUCTURE"),
    ([{"a":1},{"b":2}], "RESULT_SCHEMA"), ([{"a":float('nan')}], "NONFINITE_VALUE"),
    ([{"a":float('inf')}], "NONFINITE_VALUE"), ([{"a":1},{"a":"1"}], "RESULT_TYPE"),
    ([{"total_subjects":2,"ae_subjects":3,"ae_rate_pct":150}], "DENOMINATOR")])
def test_invalid_results(rows, code):
    assert validate_results(rows)["code"] == code


def test_grain_and_required_fields():
    rows = [{"subject":"one", "visit":1}, {"subject":"one", "visit":2}]
    assert validate_results(rows, {"business_keys":["subject","visit"]})["valid"]
    assert not validate_results(rows+[rows[0]], {"business_keys":["subject","visit"]})["valid"]
    assert not validate_results(rows, {"required_columns":["outcome"]})["valid"]
    assert validate_results([{"n":Decimal('3.25')}])["rows"] == [{"n":3.25}]


def test_sql_output_contract():
    contract = result_contract('SELECT arm AS treatment, COUNT(*) AS n FROM dm GROUP BY arm')
    assert contract["business_keys"] == ["treatment"]
    assert contract["numeric_columns"] == ["n"]
    assert not validate_results([{"treatment":"A","n":"3"}], contract)["valid"]
    assert not validate_results([{"a":1}], result_contract('SELECT x AS a, y AS a FROM dm'))["valid"]


def test_eda_null_blank_zero_sentinel_and_no_mutation():
    rows = [{"x":None, "text":""}, {"x":0,"text":" "}, {"x":-99,"text":"A"}, {"x":2,"text":"a"}]
    original = copy.deepcopy(rows)
    eda = assess_results(rows, {"columns":{"x":{"sentinels":[-99]}}})
    assert eda["missingness"]["x"]["sql_null"] == 1
    assert eda["missingness"]["x"]["specified_sentinel"] == 1
    assert eda["numeric"]["x"]["min"] == 0
    assert eda["missingness"]["text"]["empty_string"] == 1
    assert eda["missingness"]["text"]["whitespace"] == 1
    assert rows == original


def test_eda_dates_outliers_small_sample():
    rows = [{"value":v,"start":"2026-01-03","end":"2026-01-01"} for v in [1,1,1,1,100]]
    eda = assess_results(rows, {"columns":{"start":{"type":"date"},"end":{"type":"date"}}, "date_pairs":[["start","end"]]})
    assert eda["numeric"]["value"]["potential_outliers"] == 1
    assert any(f["code"] == "DATE_ORDER" for f in eda["findings"])
    assert assess_results([{"x":2}])["numeric"]["x"]["std"] is None
    assert not assess_results([{"x":None}], {"columns":{"x":{"required":True}}})["safe_to_continue"]


class RedisFixture:
    def __init__(self): self.values = {}
    def get(self,key): return self.values.get(key)
    def setex(self,key,ttl,value): self.values[key]=value
    def delete(self,key): self.values.pop(key,None)


def test_cache_integrity_expiry_invalidation_and_scope():
    redis = RedisFixture(); cache=ResultCache(redis, ttl=30)
    context={"dataset_versions":{"dm":1},"sql":"select 1", "schema":{}, "parameters":{}}
    assert cache.get(context)[1] == "miss"
    assert cache.put(context, {"rows":[{"x":1}]}) == "stored"
    assert cache.get(context)[1] == "hit"
    for changed in [{"dataset_versions":{"dm":2}},{"parameters":{"age":50}},{"schema":{"a":1}},{"sql":"select 2"}]:
        assert cache.get({**context, **changed})[1] == "miss"
    key=cache.key(context); entry=json.loads(redis.values[key]); entry['expires']=0; redis.values[key]=json.dumps(entry)
    assert cache.get(context)[1] == 'invalid'
    cache.put(context, {"rows":[]}); redis.values[key]='broken'
    assert cache.get(context)[1] == 'unavailable'
    cache.put(context, {"rows":[]}); cache.invalidate(context)
    assert cache.get(context)[1] == 'miss'
    assert cache.get({**context,"dataset_versions":{}})[1] == 'bypassed'


def test_cache_unavailable_falls_back():
    class Broken:
        def get(self,*a): raise ConnectionError('secret')
        def setex(self,*a): raise ConnectionError('secret')
    cache=ResultCache(Broken()); context={"dataset_versions":{"x":1}}
    assert cache.get(context)==(None,'unavailable')
    assert cache.put(context,{})=='unavailable'


def test_stage_retry_and_sanitization(monkeypatch):
    monkeypatch.setattr('app.workflow.runtime.record_audit_event', lambda **k: None)
    monkeypatch.setenv('WORKFLOW_MAX_RETRIES','2')
    calls=[]
    def flaky(s):
        calls.append(1)
        if len(calls)<3: raise ConnectionError('password=secret')
        return {"query_result":[{"x":1}]}
    assert stage_wrapper('execute_sql',flaky)({})['stage_status']['status']=='SUCCESS'
    assert len(calls)==3
    def unsafe(s): raise PermissionError('password=secret')
    output=stage_wrapper('execute_sql',unsafe)({})
    assert output['stage_status']['status']=='TERMINAL_FAILURE'
    assert 'secret' not in json.dumps(output)


def graph_fixture(monkeypatch, rows):
    import app.workflow.graph as g
    monkeypatch.setattr(g,'record_audit_event',lambda **kw: None)
    monkeypatch.setattr('app.workflow.runtime.record_audit_event',lambda **kw: None)
    monkeypatch.setattr(g,'load_schema',lambda s:{"database_schema":{"tables":{"dm":[]}}})
    monkeypatch.setattr(g,'analyze_question',lambda s:{"analysis_plan":"Count values"})
    monkeypatch.setattr(g,'validate_table_selection_node',lambda s:{"validation_status":"passed"})
    monkeypatch.setattr(g,'generate_sql_node',lambda s:{"sql_query":"SELECT COUNT(*) AS value FROM dm"})
    monkeypatch.setattr(g,'validate_sql_node',lambda s:{"error":""})
    monkeypatch.setattr(g,'execute_query',lambda sql: rows.pop(0) if len(rows)>1 else rows[0])
    monkeypatch.setattr(g,'generate_insight',lambda **kw:'The count is 1.')
    monkeypatch.setattr(g,'validate_insight',lambda **kw:{"valid":True})
    return g.build_graph()


def test_invalid_results_cannot_reach_insights(monkeypatch):
    graph=graph_fixture(monkeypatch,[[{"value":float('inf')}]])
    result=graph.invoke({"user_question":"Count values", "approval_status":"approved"})
    assert result['failed_node']=='validate_results'
    assert not result.get('insight') and not result.get('eda_findings')


def test_valid_results_skip_generic_eda(monkeypatch):
    import app.analytics.eda as eda_module
    monkeypatch.setattr(eda_module, 'assess_results', lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError('Generic EDA must not run')))
    graph = graph_fixture(monkeypatch, [[{"value": 1}]])
    result = graph.invoke({"user_question": "Count values", "approval_status": "approved"})
    assert result["result_validation"]["valid"] and result["chart_validation"]["valid"]
    assert not result.get("eda_findings")


def test_cache_population_follows_result_validation(monkeypatch):
    import app.workflow.graph as graph
    writes = []
    class Cache:
        def put(self, context, payload):
            writes.append(payload)
            return "stored"
    monkeypatch.setattr(graph, "_result_cache", Cache())
    monkeypatch.setattr(graph, "record_audit_event", lambda **kw: None)
    base = {"sql_query": "SELECT COUNT(*) AS value FROM dm", "user_question": "Count values"}
    invalid = graph.validate_results_node({**base, "query_result": [{"wrong": 1}]})
    assert not invalid["result_validation"]["valid"] and not writes
    valid = graph.validate_results_node({**base, "query_result": [{"value": 1}]})
    assert valid["result_validation"]["valid"] and writes == [{"rows": [{"value": 1}]}]


def test_correction_is_revalidated(monkeypatch):
    graph=graph_fixture(monkeypatch, [[{"wrong":1}],[{"value":1}]])
    result=graph.invoke({"user_question":"Count values", "approval_status":"approved"}, {"recursion_limit":100})
    assert result['result_validation']['valid'] and result['result_retry_count']==1
    assert [v['valid'] for v in result['validation_attempts']]==[False, True]
    assert result['chart_validation']['valid']


def test_result_correction_limit(monkeypatch):
    monkeypatch.setenv('RESULT_MAX_RETRIES','1')
    graph=graph_fixture(monkeypatch, [[{"wrong":1}]])
    result=graph.invoke({"user_question":"Count values", "approval_status":"approved"}, {"recursion_limit":100})
    assert result['result_retry_count']==1
    assert not result.get('insight')
    assert len(result['validation_attempts'])==2


def test_chart_and_pdf_reject_bad_output():
    with pytest.raises(ValueError): validate_chart({'chart_type':'bar','x_column':'label','y_column':'x'}, [{'label':'A','x':'bad'}])
    with pytest.raises(ValueError): validate_chart({'data':[{'x':['A'],'y':[],'name':'x'}]}, [{'x':1}])
    with pytest.raises(Exception): validate_pdf(b'%PDF-fake')


def test_durable_targeted_recovery_and_cancel_without_user_identity(monkeypatch, tmp_path):
    from sqlalchemy import create_engine
    from app.workflow import recovery
    from app.schemas.analytics import AnalyticsRequest
    from fastapi import HTTPException
    import app.workflow.graph as g
    graph_fixture(monkeypatch, [[{"value":1}]])
    monkeypatch.setattr(recovery, 'signature', lambda e,t: {"schema":{},"versions":{"dm":1}})
    engine=create_engine('sqlite:///'+str(tmp_path/'ops.sqlite'))
    initial={'user_question':'Count values','selected_tables':['dm'],'approval_status':'pending','approval_source':'api'}
    first=recovery.execute(AnalyticsRequest(question='Count values',selected_tables=['dm']),engine,initial)
    assert first['approval_status']=='pending'
    args=dict(question='Count values',selected_tables=['dm'],analysis_id=first['analysis_id'],state_version=first['state_version'],approval_status='approved')
    original_chart=g.generate_chart_node
    monkeypatch.setattr(g,'generate_chart_node',lambda s: (_ for _ in ()).throw(ConnectionError('secret')))
    failed=recovery.execute(AnalyticsRequest(**args),engine,initial)
    assert failed['failed_node']=='generate_chart'
    args['state_version']=failed['state_version']
    monkeypatch.setattr(g,'generate_chart_node',original_chart)
    monkeypatch.setattr(g,'execute_query',lambda sql: (_ for _ in ()).throw(AssertionError('SQL must not rerun')))
    completed=recovery.execute(AnalyticsRequest(**args,action='retry'),engine,initial)
    assert completed['chart_validation']['valid']
    args['state_version']=completed['state_version']
    stopped=recovery.execute(AnalyticsRequest(**args,action='stop'),engine,initial)
    assert stopped['cancelled']
    args['state_version']=stopped['state_version']
    with pytest.raises(HTTPException): recovery.execute(AnalyticsRequest(**args,action='retry'),engine,initial)


def test_saved_analysis_report_uses_validated_state(monkeypatch):
    from fastapi import HTTPException
    from app.api import analytics
    from app.workflow import store as store_module
    from app.schemas.reports import PDFReportRequest
    from tests.test_report_history import sample_pdf
    import app.analytics.eda as eda_module
    monkeypatch.setattr(eda_module, "assess_results", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("Report generation must not rerun EDA")))

    saved = {"user_question": "Trusted question", "analysis_plan": "Trusted plan",
             "result_validation": {"valid": True, "rows": [{"value": 1}]},
             "eda_findings": {"safe_to_continue": True}, "chart_validation": {"valid": True},
             "sql_query": "SELECT 1 AS value", "insight": "Observed value is 1.",
             "selected_tables": ["dm"]}
    class FakeStore:
        def __init__(self, engine): pass
        def get(self, run_id): return {"study_id": "__main_workspace__"}
        def latest_artifact(self, run_id, stage): return saved
    seen = []
    monkeypatch.setattr(store_module, "Store", FakeStore)
    monkeypatch.setattr(analytics, "build_clinical_pdf_report", lambda request: seen.append(request.model_copy(deep=True)) or sample_pdf())
    monkeypatch.setattr("app.audit.service.record_audit_event", lambda **kw: None)
    forged = PDFReportRequest(question="Forged question", results=[{"value": 999}], analysis_run_id="run-1")
    response = analytics.generate_pdf_report(forged)
    assert response.status_code == 200
    assert seen[0].question == "Trusted question" and seen[0].results == [{"value": 1}]
def test_report_renderer_retries_without_persistence(monkeypatch):
    from app.api import analytics
    from app.schemas.reports import PDFReportRequest
    from tests.test_report_history import sample_pdf
    attempts = []
    def flaky_renderer(request):
        attempts.append(True)
        if len(attempts) == 1: raise OSError("temporary renderer failure")
        return sample_pdf()
    monkeypatch.setattr(analytics, "build_clinical_pdf_report", flaky_renderer)
    monkeypatch.setattr("app.audit.service.record_audit_event", lambda **kw: None)
    response = analytics.generate_pdf_report(PDFReportRequest(question="Count values", results=[{"value": 1}]))
    assert response.status_code == 200
    assert len(attempts) == 2
