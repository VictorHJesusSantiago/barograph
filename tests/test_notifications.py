"""Tests for the notification delivery system."""

from __future__ import annotations

from barograph.notifications.manager import (
    NotificationManager,
    NotificationMessage,
)


def make_msg():
    return NotificationMessage(title="Test", body="Hello", severity="info", tags={"a": 1})


def test_console_and_file_channels(tmp_path):
    out = tmp_path / "notes.jsonl"
    manager = NotificationManager(channels=["console", "file"], file_path=out)
    results = manager.notify(make_msg())
    assert all(r.delivered for r in results)
    assert out.exists()
    content = out.read_text(encoding="utf-8").strip()
    assert '"title": "Test"' in content


def test_webhook_success_with_injected_transport():
    seen = {}

    def transport(url, body):
        seen["url"] = url
        seen["body"] = body
        return True

    manager = NotificationManager(
        channels=["webhook"],
        webhook_url="http://example.invalid/hook",
        http_transport=transport,
    )
    results = manager.notify(make_msg())
    assert results[0].delivered
    assert seen["url"] == "http://example.invalid/hook"
    assert seen["body"]["title"] == "Test"


def test_webhook_retries_then_fails():
    calls = {"n": 0}

    def transport(url, body):
        calls["n"] += 1
        raise RuntimeError("boom")

    manager = NotificationManager(
        channels=["webhook"],
        webhook_url="http://example.invalid/hook",
        max_retries=2,
        backoff_base=0.0,
        http_transport=transport,
    )
    results = manager.notify(make_msg())
    assert not results[0].delivered
    assert results[0].attempts == 3  # initial + 2 retries
    assert results[0].error == "boom"


def test_slack_payload_format():
    seen = {}

    def transport(url, body):
        seen.update(body)
        return True

    manager = NotificationManager(
        channels=["slack"],
        webhook_url="http://example.invalid/slack",
        http_transport=transport,
    )
    manager.notify(make_msg())
    assert "text" in seen
    assert "Test" in seen["text"]


def test_discord_payload_embed():
    seen = {}

    def transport(url, body):
        seen.update(body)
        return True

    manager = NotificationManager(
        channels=["discord"],
        webhook_url="http://example.invalid/discord",
        http_transport=transport,
    )
    manager.notify(make_msg())
    assert "embeds" in seen
    assert seen["embeds"][0]["title"] == "Test"


def test_unknown_channel_fails():
    manager = NotificationManager(channels=["bogus"])
    results = manager.notify(make_msg())
    assert not results[0].delivered
    assert "Unknown" in results[0].error


def test_history_and_metrics():
    def transport(url, body):
        return True

    manager = NotificationManager(
        channels=["webhook"],
        webhook_url="http://example.invalid/hook",
        http_transport=transport,
    )
    manager.notify(make_msg())
    manager.notify(make_msg())
    assert len(manager.history) == 2
    metrics = manager.delivery_metrics()
    assert metrics["sent"] == 2
    assert metrics["delivered"] == 2
    assert metrics["success_rate"] == 1.0


def test_message_roundtrip():
    msg = make_msg()
    restored = NotificationMessage.from_dict(msg.to_dict())
    assert restored.title == "Test"
    assert restored.tags == {"a": 1}


def test_unknown_channel_alone_raises_via_notify():
    # notify() catches exceptions and records them
    manager = NotificationManager(channels=["nope"])
    result = manager.notify(make_msg())[0]
    assert result.delivered is False


def test_console_does_not_write_file(tmp_path):
    manager = NotificationManager(channels=["console"])
    # ensure no file channel configured does nothing harmful
    results = manager.notify(make_msg())
    assert results[0].delivered
    assert not any(p.name == "notifications.jsonl" for p in tmp_path.iterdir())
