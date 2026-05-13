"""
tenants.py — Generate tenants-config overlay files for a versioned Foreman release.

Writes Component and ReleasePlan kustomize overlays into a local tenants-config
worktree and idempotently updates parent kustomization.yaml files.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

from lib.config import ReleaseConfig

# Matches a resource entry line in a kustomization.yaml resources block.
_RESOURCE_LINE_RE = re.compile(r"^  - .+$", re.MULTILINE)


def _write_file(path: Path, content: str, dry_run: bool) -> None:
    """Write content to path, printing status. Skip silently if already correct."""
    if path.exists():
        existing = path.read_text()
        if existing == content:
            return
        if not dry_run:
            print(f"  WARNING: Overwriting {path} (content mismatch)", file=sys.stderr)

    if dry_run:
        print(f"[dry-run] Would write {path}")
        return

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    print(f"  Wrote {path}")


def _components_kustomization_content() -> str:
    return """\
---
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
resources:
  - components.yaml
"""


def _components_yaml_content(config: ReleaseConfig) -> str:
    v = config.version
    b = config.branch_name
    return f"""\
---
apiVersion: appstudio.redhat.com/v1alpha1
kind: Component
metadata:
  annotations:
    build.appstudio.openshift.io/pipeline: '{{"name":"docker-build-oci-ta","bundle":"latest"}}'
    git-provider: github
    git-provider-url: https://github.com
  name: foreman-{v}
  namespace: theforeman-org-tenant
spec:
  application: foreman
  componentName: foreman-{v}
  containerImage: quay.io/foreman/foreman-stage
  source:
    git:
      context: images/foreman
      dockerfileUrl: Containerfile
      revision: {b}
      url: https://github.com/theforeman/foreman-oci-images.git
---
apiVersion: appstudio.redhat.com/v1alpha1
kind: Component
metadata:
  annotations:
    build.appstudio.openshift.io/pipeline: '{{"name":"docker-build-oci-ta","bundle":"latest"}}'
    git-provider: github
    git-provider-url: https://github.com
  name: foreman-proxy-{v}
  namespace: theforeman-org-tenant
spec:
  application: foreman
  componentName: foreman-proxy-{v}
  containerImage: quay.io/foreman/foreman-proxy-stage
  source:
    git:
      context: images/foreman-proxy
      dockerfileUrl: Containerfile
      revision: {b}
      url: https://github.com/theforeman/foreman-oci-images.git
"""


def _releaseplan_kustomization_content(config: ReleaseConfig) -> str:
    v = config.version
    tags = config.release_tags
    tag_lines_foreman = "\n".join(f'              - "{t}"' for t in tags)
    tag_lines_proxy = "\n".join(f'              - "{t}"' for t in tags)
    return f"""\
---
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
resources:
  - ../base
transformers:
  - |-
    apiVersion: builtin
    kind: PrefixSuffixTransformer
    metadata:
      name: SuffixTransformer
    suffix: "-{v}"
    fieldSpecs:
    - kind: ReleasePlan
      path: metadata/name
patches:
  - target:
      kind: ReleasePlan
    patch: |-
      - op: replace
        path: /spec/data/mapping/components
        value:
          - name: foreman-{v}
            repository: quay.io/foreman/foreman
            tags:
{tag_lines_foreman}
          - name: foreman-proxy-{v}
            repository: quay.io/foreman/foreman-proxy
            tags:
{tag_lines_proxy}
"""


def _insert_resource_entry(content: str, entry: str, path: "Path | None" = None) -> str:
    """Insert '  - entry/' after the last resource line in the resources block."""
    entry_line = f"  - {entry}/"
    matches = list(_RESOURCE_LINE_RE.finditer(content))
    if not matches:
        location = str(path) if path is not None else "<unknown>"
        raise RuntimeError(
            f"Cannot insert resource: no existing resource entries found in {location}. "
            "Manual edit required."
        )
    last_match = matches[-1]
    insert_pos = last_match.end()
    return content[:insert_pos] + f"\n{entry_line}" + content[insert_pos:]


def _update_parent_kustomization(kustomization_path: Path, version: str, dry_run: bool) -> None:
    """Idempotently add '  - {version}/' to the resources list in kustomization_path."""
    entry_line = f"  - {version}/"
    content = kustomization_path.read_text()
    if entry_line in content.splitlines():
        return
    new_content = _insert_resource_entry(content, version, path=kustomization_path)
    if dry_run:
        print(f"[dry-run] Would write {kustomization_path}")
        return
    kustomization_path.write_text(new_content)
    print(f"  Wrote {kustomization_path}")


def generate_component_overlay(config: ReleaseConfig, tenant_path: Path, dry_run: bool) -> None:
    """Generate components/<VERSION>/ kustomization.yaml and components.yaml."""
    overlay_dir = tenant_path / "components" / config.version
    if not dry_run:
        overlay_dir.mkdir(parents=True, exist_ok=True)

    _write_file(overlay_dir / "kustomization.yaml", _components_kustomization_content(), dry_run)
    _write_file(overlay_dir / "components.yaml", _components_yaml_content(config), dry_run)


def generate_releaseplan_overlay(config: ReleaseConfig, tenant_path: Path, dry_run: bool) -> None:
    """Generate releaseplans/<VERSION>/kustomization.yaml."""
    overlay_dir = tenant_path / "releaseplans" / config.version
    if not dry_run:
        overlay_dir.mkdir(parents=True, exist_ok=True)

    _write_file(overlay_dir / "kustomization.yaml", _releaseplan_kustomization_content(config), dry_run)


def update_parent_kustomizations(config: ReleaseConfig, tenant_path: Path, dry_run: bool) -> None:
    """Add <VERSION>/ to components/ and releaseplans/ parent kustomization.yaml files."""
    components_kust = tenant_path / "components" / "kustomization.yaml"
    releaseplans_kust = tenant_path / "releaseplans" / "kustomization.yaml"

    _update_parent_kustomization(components_kust, config.version, dry_run)
    _update_parent_kustomization(releaseplans_kust, config.version, dry_run)
