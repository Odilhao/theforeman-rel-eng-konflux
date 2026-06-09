"""Tests for lib.tenants — overlay generation and parent kustomization updates."""

from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

import pytest

_BR = Path(__file__).parents[1]
if str(_BR) not in sys.path:
    sys.path.insert(0, str(_BR))

from lib.config import ReleaseConfig  # noqa: E402
from lib.tenants import (  # noqa: E402
    _PROJECTS,
    _insert_resource_entry,
    generate_component_overlay,
    generate_releaseplan_overlay,
    project_for_repo,
    update_parent_kustomizations,
)

SAMPLE_CONFIG = ReleaseConfig(
    version="3.19",
    branch_name="foreman-3.19",
    foreman_tag="foreman-3.19",
    foreman_xyz_tag="foreman-3.19.0",
    oci_repos=["theforeman/foreman-oci-images"],
    release_tags=["3.19", "3.19.0"],
    version_xyz="3.19.0",
    rpm_check_url="https://example.com",
    rpm_check_timeout=3600,
    katello_version="4.15",
    pulp_version="3.105",
    candlepin_version="4.7",
    candlepin_version_xyz="4.7.4",
)

# Parent kustomization.yaml content as it would exist in tenants-config before branching.
_PARENT_COMPONENTS_KUSTOMIZATION = """\
---
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
resources:
  - develop/
"""

_PARENT_RELEASEPLANS_KUSTOMIZATION = """\
---
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
resources:
  - develop/
namespace: theforeman-org-tenant
"""


def _make_tenant_tree(tmp_path: Path) -> Path:
    """Create the minimum tenants-config directory structure under tmp_path."""
    tenant_path = tmp_path / "foreman"
    (tenant_path / "components").mkdir(parents=True)
    (tenant_path / "releaseplans").mkdir(parents=True)
    (tenant_path / "components" / "kustomization.yaml").write_text(_PARENT_COMPONENTS_KUSTOMIZATION)
    (tenant_path / "releaseplans" / "kustomization.yaml").write_text(_PARENT_RELEASEPLANS_KUSTOMIZATION)
    return tenant_path


class TestGenerateComponentOverlay(unittest.TestCase):

    def test_creates_kustomization_and_components_yaml(self) -> None:
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, True)
        tenant_path = _make_tenant_tree(Path(tmp))
        generate_component_overlay(SAMPLE_CONFIG, _PROJECTS["foreman-oci-images"], tenant_path, dry_run=False)

        overlay_dir = tenant_path / "components" / "3.19"
        kust = overlay_dir / "kustomization.yaml"
        comp = overlay_dir / "components.yaml"

        self.assertTrue(kust.exists(), "kustomization.yaml must be created")
        self.assertTrue(comp.exists(), "components.yaml must be created")

        kust_text = kust.read_text()
        self.assertTrue(kust_text.startswith("---"), "kustomization.yaml must start with ---")
        self.assertIn("components.yaml", kust_text)

        comp_text = comp.read_text()
        self.assertTrue(comp_text.startswith("---"), "components.yaml must start with ---")
        self.assertIn("foreman-3-19", comp_text)
        self.assertIn("foreman-proxy-3-19", comp_text)
        self.assertIn("revision: foreman-3.19", comp_text)
        self.assertIn("quay.io/foreman/stage/foreman", comp_text)
        self.assertIn("quay.io/foreman/stage/foreman-proxy", comp_text)
        self.assertIn("images/foreman", comp_text)
        self.assertIn("images/foreman-proxy", comp_text)
        self.assertIn("theforeman-org-tenant", comp_text)

    def test_idempotent_second_call_does_not_raise(self) -> None:
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, True)
        tenant_path = _make_tenant_tree(Path(tmp))
        generate_component_overlay(SAMPLE_CONFIG, _PROJECTS["foreman-oci-images"], tenant_path, dry_run=False)
        # Second call must not raise and content must remain unchanged.
        generate_component_overlay(SAMPLE_CONFIG, _PROJECTS["foreman-oci-images"], tenant_path, dry_run=False)

        comp_text = (tenant_path / "components" / "3.19" / "components.yaml").read_text()
        self.assertIn("foreman-3-19", comp_text)

    def test_dry_run_writes_no_files(self) -> None:
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, True)
        tenant_path = _make_tenant_tree(Path(tmp))
        generate_component_overlay(SAMPLE_CONFIG, _PROJECTS["foreman-oci-images"], tenant_path, dry_run=True)

        overlay_dir = tenant_path / "components" / "3.19"
        self.assertFalse((overlay_dir / "kustomization.yaml").exists())
        self.assertFalse((overlay_dir / "components.yaml").exists())


class TestGenerateReleaseplanOverlay(unittest.TestCase):

    def test_creates_kustomization_yaml(self) -> None:
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, True)
        tenant_path = _make_tenant_tree(Path(tmp))
        generate_releaseplan_overlay(SAMPLE_CONFIG, _PROJECTS["foreman-oci-images"], tenant_path, dry_run=False)

        overlay_dir = tenant_path / "releaseplans" / "3.19"
        kust = overlay_dir / "kustomization.yaml"

        self.assertTrue(kust.exists(), "releaseplans kustomization.yaml must be created")
        text = kust.read_text()
        self.assertTrue(text.startswith("---"), "must start with ---")
        self.assertIn("foreman-3-19", text)
        self.assertIn("foreman-proxy-3-19", text)
        self.assertIn('"3.19"', text)
        self.assertIn('"3.19.0"', text)
        self.assertIn("repositories:", text)
        self.assertIn("url: quay.io/foreman/foreman", text)
        self.assertIn("url: quay.io/foreman/foreman-proxy", text)
        self.assertNotIn("repository:", text, "old flat format must not appear")
        self.assertNotIn("foreman-stage", text, "production image must not have -stage suffix")
        self.assertIn("../base", text)
        self.assertIn('suffix: "-3-19"', text)
        self.assertNotIn("singleComponentMode", text, "foreman project must not have singleComponentMode")

    def test_tags_come_from_release_tags(self) -> None:
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, True)
        tmp_path = Path(tmp)
        cfg = ReleaseConfig(
            version="3.20",
            branch_name="foreman-3.20",
            foreman_tag="foreman-3.20",
            foreman_xyz_tag="foreman-3.20.0",
            oci_repos=["theforeman/foreman-oci-images"],
            release_tags=["3.20", "3.20.0", "3.20.1"],
            version_xyz="3.20.0",
            rpm_check_url="https://example.com",
            rpm_check_timeout=3600,
            katello_version="4.16",
            pulp_version="3.105",
            candlepin_version="4.8",
            candlepin_version_xyz="4.8.0",
        )
        (tmp_path / "releaseplans").mkdir(parents=True)
        generate_releaseplan_overlay(cfg, _PROJECTS["foreman-oci-images"], tmp_path, dry_run=False)

        text = (tmp_path / "releaseplans" / "3.20" / "kustomization.yaml").read_text()
        self.assertIn('"3.20"', text)
        self.assertIn('"3.20.0"', text)
        self.assertIn('"3.20.1"', text)

    def test_dry_run_writes_no_files(self) -> None:
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, True)
        tenant_path = _make_tenant_tree(Path(tmp))
        generate_releaseplan_overlay(SAMPLE_CONFIG, _PROJECTS["foreman-oci-images"], tenant_path, dry_run=True)

        overlay_dir = tenant_path / "releaseplans" / "3.19"
        self.assertFalse((overlay_dir / "kustomization.yaml").exists())


class TestUpdateParentKustomizations(unittest.TestCase):

    def test_adds_version_entry_to_both_parents(self) -> None:
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, True)
        tenant_path = _make_tenant_tree(Path(tmp))
        update_parent_kustomizations(SAMPLE_CONFIG, tenant_path, dry_run=False)

        comp_kust = (tenant_path / "components" / "kustomization.yaml").read_text()
        rp_kust = (tenant_path / "releaseplans" / "kustomization.yaml").read_text()
        self.assertIn("  - 3.19/", comp_kust)
        self.assertIn("  - 3.19/", rp_kust)

    def test_idempotent_does_not_duplicate_entry(self) -> None:
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, True)
        tenant_path = _make_tenant_tree(Path(tmp))
        update_parent_kustomizations(SAMPLE_CONFIG, tenant_path, dry_run=False)
        update_parent_kustomizations(SAMPLE_CONFIG, tenant_path, dry_run=False)

        comp_kust = (tenant_path / "components" / "kustomization.yaml").read_text()
        count = comp_kust.count("  - 3.19/")
        self.assertEqual(count, 1, "version entry must appear exactly once")

    def test_dry_run_does_not_modify_files(self) -> None:
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, True)
        tenant_path = _make_tenant_tree(Path(tmp))
        before_comp = (tenant_path / "components" / "kustomization.yaml").read_text()
        before_rp = (tenant_path / "releaseplans" / "kustomization.yaml").read_text()

        update_parent_kustomizations(SAMPLE_CONFIG, tenant_path, dry_run=True)

        after_comp = (tenant_path / "components" / "kustomization.yaml").read_text()
        after_rp = (tenant_path / "releaseplans" / "kustomization.yaml").read_text()
        self.assertEqual(before_comp, after_comp)
        self.assertEqual(before_rp, after_rp)

    def test_namespace_field_preserved_after_insert(self) -> None:
        """Inserting a resource entry must not corrupt fields after the resources block."""
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, True)
        tenant_path = _make_tenant_tree(Path(tmp))
        update_parent_kustomizations(SAMPLE_CONFIG, tenant_path, dry_run=False)

        rp_kust = (tenant_path / "releaseplans" / "kustomization.yaml").read_text()
        self.assertIn("namespace: theforeman-org-tenant", rp_kust)
        self.assertIn("  - 3.19/", rp_kust)


class TestInsertResourceEntryFallback(unittest.TestCase):

    def test_empty_resources_block_inserts_correctly(self) -> None:
        """Empty resources: block (no entries) must accept insertion without error."""
        content = """\
---
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
resources:
namespace: theforeman-org-tenant
"""
        result = _insert_resource_entry(content, "3.19")
        self.assertIn("  - 3.19/", result)
        self.assertIn("namespace: theforeman-org-tenant", result)

    def test_raises_when_no_resources_key(self) -> None:
        """_insert_resource_entry must raise RuntimeError when there is no resources: key."""
        content = """\
---
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
namespace: theforeman-org-tenant
"""
        with self.assertRaises(RuntimeError) as ctx:
            _insert_resource_entry(content, "3.19")
        self.assertIn("no resources: block found", str(ctx.exception))
        self.assertIn("Manual edit required", str(ctx.exception))

    def test_does_not_insert_into_patches_block(self) -> None:
        """New entry must appear inside resources:, not after patches: or other arrays."""
        content = "resources:\n  - develop/\npatches:\n  - path: foo.yaml\n"
        result = _insert_resource_entry(content, "3.19")
        self.assertEqual(result.count("  - 3.19/"), 1)
        # Must appear before patches:, not after
        resources_pos = result.index("resources:")
        patches_pos = result.index("patches:")
        new_entry_pos = result.index("  - 3.19/")
        self.assertLess(resources_pos, new_entry_pos)
        self.assertLess(new_entry_pos, patches_pos)


class TestGeneratePulpOverlay(unittest.TestCase):

    def test_creates_pulp_component(self) -> None:
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, True)
        tmp_path = Path(tmp)
        (tmp_path / "components").mkdir(parents=True)
        generate_component_overlay(SAMPLE_CONFIG, _PROJECTS["pulp-oci-images"], tmp_path, dry_run=False)

        comp_text = (tmp_path / "components" / "3.19" / "components.yaml").read_text()
        self.assertIn("pulp-3-19", comp_text)
        self.assertIn("images/pulp/Containerfile", comp_text)
        self.assertNotIn("name: foreman-3-19", comp_text)
        self.assertNotIn("componentName: foreman-3-19", comp_text)

    def test_creates_pulp_releaseplan_with_single_component_mode(self) -> None:
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, True)
        tmp_path = Path(tmp)
        (tmp_path / "releaseplans").mkdir(parents=True)
        generate_releaseplan_overlay(SAMPLE_CONFIG, _PROJECTS["pulp-oci-images"], tmp_path, dry_run=False)

        text = (tmp_path / "releaseplans" / "3.19" / "kustomization.yaml").read_text()
        self.assertIn("singleComponentMode: true", text)
        self.assertIn("pulp-3-19", text)
        self.assertIn("quay.io/foreman/pulp\n", text)
        self.assertNotIn("pulp-stage", text)


class TestGenerateCandlepinOverlay(unittest.TestCase):

    def test_creates_candlepin_component(self) -> None:
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, True)
        tmp_path = Path(tmp)
        (tmp_path / "components").mkdir(parents=True)
        generate_component_overlay(SAMPLE_CONFIG, _PROJECTS["candlepin-oci-images"], tmp_path, dry_run=False)

        comp_text = (tmp_path / "components" / "3.19" / "components.yaml").read_text()
        self.assertIn("candlepin-3-19", comp_text)
        self.assertNotIn("name: foreman-3-19", comp_text)
        self.assertNotIn("componentName: foreman-3-19", comp_text)

    def test_creates_candlepin_releaseplan_with_single_component_mode(self) -> None:
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, True)
        tmp_path = Path(tmp)
        (tmp_path / "releaseplans").mkdir(parents=True)
        generate_releaseplan_overlay(SAMPLE_CONFIG, _PROJECTS["candlepin-oci-images"], tmp_path, dry_run=False)

        text = (tmp_path / "releaseplans" / "3.19" / "kustomization.yaml").read_text()
        self.assertIn("singleComponentMode: true", text)
        self.assertIn("candlepin-3-19", text)
        self.assertIn("quay.io/foreman/candlepin\n", text)
        self.assertNotIn("candlepin-stage", text)


# --- pytest-style tests ---


def test_project_for_repo_known() -> None:
    p = project_for_repo("theforeman/pulp-oci-images")
    assert p.app_name == "pulp"


def test_project_for_repo_unknown_raises() -> None:
    with pytest.raises(KeyError):
        project_for_repo("theforeman/unknown-repo")


def test_generate_component_overlay_creates_files(tmp_path: Path) -> None:
    tenant_path = _make_tenant_tree(tmp_path)
    generate_component_overlay(SAMPLE_CONFIG, _PROJECTS["foreman-oci-images"], tenant_path, dry_run=False)
    assert (tenant_path / "components" / "3.19" / "kustomization.yaml").exists()
    assert (tenant_path / "components" / "3.19" / "components.yaml").exists()


def test_generate_releaseplan_overlay_creates_file(tmp_path: Path) -> None:
    tenant_path = _make_tenant_tree(tmp_path)
    generate_releaseplan_overlay(SAMPLE_CONFIG, _PROJECTS["foreman-oci-images"], tenant_path, dry_run=False)
    assert (tenant_path / "releaseplans" / "3.19" / "kustomization.yaml").exists()


def test_update_parent_kustomizations_idempotent(tmp_path: Path) -> None:
    tenant_path = _make_tenant_tree(tmp_path)
    update_parent_kustomizations(SAMPLE_CONFIG, tenant_path, dry_run=False)
    update_parent_kustomizations(SAMPLE_CONFIG, tenant_path, dry_run=False)
    text = (tenant_path / "components" / "kustomization.yaml").read_text()
    assert text.count("  - 3.19/") == 1


@pytest.mark.parametrize("dry_run", [True, False])
def test_component_overlay_dry_run_param(tmp_path: Path, dry_run: bool) -> None:
    tenant_path = _make_tenant_tree(tmp_path)
    generate_component_overlay(SAMPLE_CONFIG, _PROJECTS["foreman-oci-images"], tenant_path, dry_run=dry_run)
    overlay_exists = (tenant_path / "components" / "3.19" / "components.yaml").exists()
    if dry_run:
        assert not overlay_exists
    else:
        assert overlay_exists


if __name__ == "__main__":
    unittest.main()
