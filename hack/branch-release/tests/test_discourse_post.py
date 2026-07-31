"""Tests for discourse_post — template rendering."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_BR = Path(__file__).parents[1]
if str(_BR) not in sys.path:
    sys.path.insert(0, str(_BR))

import importlib  # noqa: E402
import importlib.machinery  # noqa: E402
import importlib.util  # noqa: E402
import types  # noqa: E402

from lib.config import load_config  # noqa: E402


def _load_discourse_post() -> types.ModuleType:
    source_path = _BR / "discourse_post"
    loader = importlib.machinery.SourceFileLoader("discourse_post", str(source_path))
    spec = importlib.util.spec_from_loader("discourse_post", loader)
    assert spec is not None
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


@pytest.fixture(scope="session")
def dp():
    return _load_discourse_post()


# ---------------------------------------------------------------------------
# render() — output content checks against the real 3.19 settings
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def cfg():
    return load_config("3.19")


@pytest.fixture(scope="session")
def rendered(dp):
    return dp.render("3.19", "discourse-oci-branching.md.j2")


def test_render_contains_version(rendered):
    assert "3.19" in rendered


def test_render_contains_branch_name(rendered):
    assert "foreman-3.19" in rendered


def test_render_contains_all_oci_repos(rendered):
    assert "foreman-oci-images" in rendered
    assert "pulp-oci-images" in rendered
    assert "candlepin-oci-images" in rendered


def test_render_contains_release_tags(rendered, cfg):
    for tag in cfg.release_tags:
        assert tag in rendered, f"release tag {tag!r} not found in rendered output"


def test_render_contains_pulp_version(rendered, cfg):
    assert cfg.pulp_version in rendered


def test_render_contains_candlepin_versions(rendered, cfg):
    assert cfg.candlepin_version in rendered
    assert cfg.candlepin_version_xyz in rendered


def test_render_contains_checklist_items(rendered):
    assert "- [ ]" in rendered


def test_render_contains_quay_images(rendered):
    assert "quay.io/foreman/foreman:" in rendered
    assert "quay.io/foreman/pulp:" in rendered
    assert "quay.io/foreman/candlepin:" in rendered


def test_render_contains_gh_links(rendered):
    assert "https://github.com/theforeman/foreman-oci-images" in rendered
    assert "https://github.com/theforeman/pulp-oci-images" in rendered
    assert "https://github.com/theforeman/candlepin-oci-images" in rendered


def test_render_no_unfilled_placeholders(rendered):
    """No raw Jinja2 tags should survive rendering."""
    assert "{{" not in rendered
    assert "}}" not in rendered


# ---------------------------------------------------------------------------
# _repo_name filter
# ---------------------------------------------------------------------------


def test_repo_name_filter(dp):
    assert dp._repo_name("theforeman/foreman-oci-images") == "foreman-oci-images"
    assert dp._repo_name("foo/bar/baz") == "baz"
    assert dp._repo_name("simple") == "simple"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def test_parse_args_version(dp, monkeypatch):
    monkeypatch.setattr(sys, "argv", ["discourse_post", "--version=3.19"])
    args = dp._parse_args()
    assert args.version == "3.19"
    assert args.template == "discourse-oci-branching.md.j2"


def test_parse_args_custom_template(dp, monkeypatch):
    monkeypatch.setattr(sys, "argv", ["discourse_post", "--version=3.19", "--template=custom.j2"])
    args = dp._parse_args()
    assert args.template == "custom.j2"


def test_parse_args_version_required(dp, monkeypatch):
    monkeypatch.setattr(sys, "argv", ["discourse_post"])
    with pytest.raises(SystemExit) as exc_info:
        dp._parse_args()
    assert exc_info.value.code == 2
