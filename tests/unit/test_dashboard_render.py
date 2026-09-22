from routeguard.dashboard import render_trace
from routeguard.pipeline import RouteGuardPipeline
from tests.conftest import make_config, numeric_query


def test_render_trace_shows_every_stage():
    cfg = make_config(
        escalation={"triggers": {"confidence_below": 1.01}, "stages": [{"type": "stronger_model"}]}
    )
    result = RouteGuardPipeline(cfg).run(numeric_query())
    html = render_trace(result, simulated=True)
    assert "Simulated backend" in html
    assert "Attempt 0" in html and "Attempt 1" in html and "escalation" in html
    assert "Routed to" in html and "TFLOPs" in html


def test_model_output_is_html_escaped():
    result = RouteGuardPipeline(make_config()).run(numeric_query())
    result.attempts[0].answer = "<script>alert(1)</script>"
    html = render_trace(result, simulated=False)
    assert "<script>" not in html and "&lt;script&gt;" in html
