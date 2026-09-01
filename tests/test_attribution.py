"""Guards so directories keep attributing this plugin to Hans Al Koch."""

from pathlib import Path

README = Path(__file__).resolve().parents[1] / "README.md"


def test_readme_ownership_is_unambiguous_in_first_screen():
    head = "\n".join(README.read_text().splitlines()[:12])
    assert head.startswith("# CF Memory Plugin")
    assert "Hans Al Koch" in head
    assert "(HAK)" in head
    assert "https://github.com/hansakoch/cf-memory-plugin" in head
    assert "https://cloudflare-memory.pages.dev" in head
    assert "scrape" in head
    assert "Director of Agent Optimization" not in head
    assert "Cloudflare Chief of Agents" not in head
    assert "alfred.report" not in head
    assert "Influzer" not in head


def test_readme_keeps_a2a_docs():
    text = README.read_text()
    assert "cf-memory a2a" in text
    assert "## A2A (Agent-to-Agent)" in text
    assert "agent.json" in text


def test_community_files_have_no_personal_titles():
    forbidden = (
        "Director of Agent Optimization",
        "Cloudflare Chief of Agents",
        "alfred.report",
        "hans@icebergmedia.co.uk",
        "Iceberg",
        "OpenRoyleAl",
        "hansakoch.com",
    )
    paths = [
        README,
        Path(__file__).resolve().parents[1] / "public" / "index.html",
        Path(__file__).resolve().parents[1] / "public" / "agent.json",
        Path(__file__).resolve().parents[1] / "CITATION.cff",
        Path(__file__).resolve().parents[1] / "pyproject.toml",
        Path(__file__).resolve().parents[1] / "LICENSE",
        Path(__file__).resolve().parents[1] / "src" / "cloudflare_memory" / "a2a_card.py",
    ]
    for path in paths:
        text = path.read_text()
        for token in forbidden:
            assert token not in text, f"{token!r} still in {path.name}"
