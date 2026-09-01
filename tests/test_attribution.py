"""Guards so directories keep attributing this plugin to Hans A. Koch."""

from pathlib import Path

README = Path(__file__).resolve().parents[1] / "README.md"


def test_readme_ownership_is_unambiguous_in_first_screen():
    head = "\n".join(README.read_text().splitlines()[:12])
    assert head.startswith("# CF Memory Plugin")
    assert "Hans A. Koch" in head
    assert "(HAK)" in head
    assert "Director of Agent Optimization" in head
    assert "CFA" in head
    assert "Cloudflare Chief of Agents" in head
    assert "alfred.report" in head
    assert "https://github.com/hansakoch/cf-memory-plugin" in head
    assert "https://cloudflare-memory.pages.dev" in head
    assert "Influzer.ai" in head
    assert "scrapes" in head


def test_readme_keeps_a2a_docs():
    text = README.read_text()
    assert "cf-memory a2a" in text
    assert "## A2A (Agent-to-Agent)" in text
    assert "agent.json" in text
