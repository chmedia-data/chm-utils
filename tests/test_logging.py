import logging

import pytest
import requests

from chm_utils import logging as chm_logging


class _Resp:
    def __init__(self, status, body):
        self.status_code = status
        self._body = body

    def json(self):
        return self._body


@pytest.fixture()
def slack_env(monkeypatch):
    monkeypatch.setenv("SLACK_TOKEN", "xoxb-test")
    monkeypatch.setenv("SLACK_CHANNEL_ID", "C123")


def _record(msg="boom"):
    return logging.LogRecord("t", logging.ERROR, __file__, 1, msg, None, None)


def test_get_logger_attaches_a_handler_instance(slack_env):
    logger = chm_logging.getLogger("test-instance")
    slack = [h for h in logger.handlers if isinstance(h, chm_logging.SlackHandler)]
    assert len(slack) == 1


def test_get_logger_skips_slack_without_credentials(monkeypatch):
    monkeypatch.delenv("SLACK_TOKEN", raising=False)
    logger = chm_logging.getLogger("test-no-creds")
    assert not any(isinstance(h, chm_logging.SlackHandler) for h in logger.handlers)


def test_get_logger_does_not_stack_handlers(slack_env):
    first = chm_logging.getLogger("test-twice")
    n = len(first.handlers)
    assert len(chm_logging.getLogger("test-twice").handlers) == n


def test_get_logger_can_opt_out_of_slack(slack_env):
    logger = chm_logging.getLogger("test-opt-out", slack=False)
    assert not any(isinstance(h, chm_logging.SlackHandler) for h in logger.handlers)


def test_emit_posts_with_a_timeout(slack_env, monkeypatch):
    sent = {}

    def post(url, **kwargs):
        sent.update(kwargs)
        return _Resp(200, {"ok": True})

    monkeypatch.setattr(requests, "post", post)
    chm_logging.SlackHandler().emit(_record())
    assert sent["timeout"] == 5
    assert sent["json"]["channel"] == "C123"
    assert "boom" in sent["json"]["text"]


def test_emit_reports_slack_ok_false(slack_env, monkeypatch, capsys):
    monkeypatch.setattr(requests, "post", lambda *a, **k: _Resp(200, {"ok": False, "error": "not_in_channel"}))
    chm_logging.SlackHandler().emit(_record())
    assert "not_in_channel" in capsys.readouterr().out


def test_emit_never_raises(slack_env, monkeypatch, capsys):
    def post(*a, **k):
        raise requests.Timeout("slow")

    monkeypatch.setattr(requests, "post", post)
    chm_logging.SlackHandler().emit(_record())
    assert "Timeout" in capsys.readouterr().out


def test_package_logger_never_posts_to_slack(slack_env):
    import chm_utils

    assert not any(isinstance(h, chm_logging.SlackHandler) for h in chm_utils.__logger__.handlers)
