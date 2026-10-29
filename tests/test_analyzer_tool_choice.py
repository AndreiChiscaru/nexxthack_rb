import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from app.analyzer import AnalysisError, REPORT_TOOL, _request


def client_with(*blocks, stop_reason="end_turn"):
    return SimpleNamespace(messages=SimpleNamespace(create=Mock(return_value=SimpleNamespace(
        content=list(blocks), stop_reason=stop_reason))))


def test_statement_request_uses_supported_auto_tool_choice():
    report = {"moneda": "RON", "rezumat": "Date fictive"}
    client = client_with(SimpleNamespace(type="tool_use", name="raport_extras", input=report))
    assert _request(client, "extras fictiv", use_tool=True) == report
    request = client.messages.create.call_args.kwargs
    assert request["tool_choice"] == {"type": "auto"}
    assert request["tools"] == [REPORT_TOOL]


def test_auto_tool_choice_accepts_json_text_without_a_tool_call():
    report = {"moneda": "RON", "rezumat": "Date fictive"}
    client = client_with(SimpleNamespace(type="text", text=json.dumps(report)))
    assert _request(client, "extras fictiv", use_tool=True) == report


def test_json_retry_does_not_send_tools_or_forced_choice():
    client = client_with(SimpleNamespace(type="text", text='{"moneda":"RON"}'))
    assert _request(client, "extras fictiv", use_tool=False) == {"moneda": "RON"}
    assert "tool_choice" not in client.messages.create.call_args.kwargs
    assert "tools" not in client.messages.create.call_args.kwargs


def test_truncated_report_is_rejected():
    client = client_with(SimpleNamespace(type="text", text='{"moneda":"RON"}'), stop_reason="max_tokens")
    with pytest.raises(AnalysisError, match="limita modelului"):
        _request(client, "extras fictiv", use_tool=True)


@pytest.mark.parametrize("use_tool", [True, False])
def test_sonnet_55_reserves_output_for_the_report(monkeypatch, use_tool):
    monkeypatch.setattr("app.analyzer.MODEL", "claude-sonnet-5-5")
    client = client_with(SimpleNamespace(type="text", text='{"moneda":"RON"}'))
    _request(client, "extras fictiv", use_tool=use_tool)
    request = client.messages.create.call_args.kwargs
    assert request["thinking"] == {"type": "between_tools"}
    assert request["output_config"] == {"effort": "medium"}


def test_other_models_keep_their_default_thinking(monkeypatch):
    monkeypatch.setattr("app.analyzer.MODEL", "claude-sonnet-4-5")
    client = client_with(SimpleNamespace(type="text", text='{"moneda":"RON"}'))
    _request(client, "extras fictiv", use_tool=False)
    assert "thinking" not in client.messages.create.call_args.kwargs


@pytest.mark.parametrize("use_tool", [True, False])
def test_haiku_55_reserves_output_for_the_report(monkeypatch, use_tool):
    monkeypatch.setattr("app.analyzer.MODEL", "claude-haiku-5-5")
    client = client_with(SimpleNamespace(type="text", text='{"moneda":"RON"}'))
    _request(client, "extras fictiv", use_tool=use_tool)
    request = client.messages.create.call_args.kwargs
    assert request["thinking"] == {"type": "disabled"}
    assert request["output_config"] == {"effort": "medium"}


def test_precomputed_monthly_totals_reach_analyzer_without_removing_source(monkeypatch):
    stats = {"luni": 12, "cheltuieli_medii": 2507.05, "categorii": []}
    monkeypatch.setattr("app.analyzer.summarize", lambda text: stats)
    client = client_with(SimpleNamespace(type="text", text='{"moneda":"RON"}'))
    _request(client, "original complete statement", use_tool=True)
    content = client.messages.create.call_args.kwargs["messages"][0]["content"]
    assert "original complete statement" in content
    assert "2507.05" in content
    assert "medii_calculate" in content


def test_unrecognized_statement_does_not_claim_precomputed_totals(monkeypatch):
    monkeypatch.setattr("app.analyzer.summarize", lambda text: None)
    client = client_with(SimpleNamespace(type="text", text='{"moneda":"RON"}'))
    _request(client, "unrecognized source", use_tool=True)
    content = client.messages.create.call_args.kwargs["messages"][0]["content"]
    assert "unrecognized source" in content
    assert "medii_calculate" not in content
