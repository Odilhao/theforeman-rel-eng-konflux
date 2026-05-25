"""
tenants.py — Generate tenants-config overlay files for a versioned Foreman release.

Writes Component and ReleasePlan kustomize overlays into a local tenants-config
worktree and idempotently updates parent kustomization.yaml files.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass as _dataclass
from pathlib import Path

from lib.config import ReleaseConfig

# Matches the resources: block followed by zero or more "  - ..." lines.
_RESOURCES_BLOCK_RE = re.compile(r"^resources:\n((?:  - .+\n)*)", re.MULTILINE)


@_dataclass(frozen=True)
class _ComponentSpec:
    name_base: str       # e.g. "pulp" → component named "pulp-{version}"
    context: str         # e.g. "images/pulp"
    dockerfile_url: str  # e.g. "Containerfile" or "images/pulp/Containerfile"
    staging_image: str   # e.g. "quay.io/foreman/pulp-stage"
    prod_image: str      # e.g. "quay.io/foreman/pulp"
    repo_url: str        # e.g. "https://github.com/theforeman/pulp-oci-images.git"


@_dataclass(frozen=True)
class _ProjectSpec:
    app_name: str                           # e.g. "pulp"
    components: tuple[_ComponentSpec, ...]  # one or more
    single_component_mode: bool             # True for single-component projects


_PROJECTS: dict[str, _ProjectSpec] = {
    "foreman-oci-images": _ProjectSpec(
        app_name="foreman",
        single_component_mode=False,
        components=(
            _ComponentSpec("foreman", "images/foreman", "Containerfile",
                           "quay.io/foreman/foreman-stage", "quay.io/foreman/foreman",
                           "https://github.com/theforeman/foreman-oci-images.git"),
            _ComponentSpec("foreman-proxy", "images/foreman-proxy", "Containerfile",
                           "quay.io/foreman/foreman-proxy-stage", "quay.io/foreman/foreman-proxy",
                           "https://github.com/theforeman/foreman-oci-images.git"),
        ),
    ),
    "pulp-oci-images": _ProjectSpec(
        app_name="pulp",
        single_component_mode=True,
        components=(
            _ComponentSpec("pulp", "images/pulp", "images/pulp/Containerfile",
                           "quay.io/foreman/pulp-stage", "quay.io/foreman/pulp",
                           "https://github.com/theforeman/pulp-oci-images.git"),
        ),
    ),
    "candlepin-oci-images": _ProjectSpec(
        app_name="candlepin",
        single_component_mode=True,
        components=(
            _ComponentSpec("candlepin", "images/candlepin", "Containerfile",
                           "quay.io/foreman/candlepin-stage", "quay.io/foreman/candlepin",
                           "https://github.com/theforeman/candlepin-oci-images.git"),
        ),
    ),
}


def project_for_repo(repo: str) -> "_ProjectSpec":
    """Return the project spec for a repo like 'theforeman/pulp-oci-images'."""
    repo_name = repo.split("/")[-1]
    if repo_name not in _PROJECTS:
        raise KeyError(f"Unknown OCI repo: {repo!r}. Known repos: {', '.join(_PROJECTS)}")
    return _PROJECTS[repo_name]


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
  - application.yaml
  - components.yaml
"""


def _application_yaml_content(config: ReleaseConfig, project: "_ProjectSpec") -> str:
    """Generate a versioned Application CRD (e.g. pulp-3-19).

    Versioned components must live in their own Application so that
    Konflux snapshots are scoped to only the versioned components.
    Without this, a build of pulp-3-19 would create a snapshot that
    also includes pulp-develop, causing both ReleasePlans to fire.
    """
    v = config.version.replace(".", "-")
    app_name = f"{project.app_name}-{v}"
    display = f"{project.app_name.capitalize()} {config.version}"
    return f"""\
---
apiVersion: appstudio.redhat.com/v1alpha1
kind: Application
metadata:
  name: {app_name}
  namespace: theforeman-org-tenant
spec:
  displayName: {display}
"""


def _components_yaml_content(config: ReleaseConfig, project: "_ProjectSpec") -> str:
    v = config.version.replace(".", "-")  # dots invalid in Kubernetes names
    b = config.branch_name
    versioned_app = f"{project.app_name}-{v}"  # own Application per version
    parts: list[str] = []
    for comp in project.components:
        parts.append(f"""\
---
apiVersion: appstudio.redhat.com/v1alpha1
kind: Component
metadata:
  annotations:
    build.appstudio.openshift.io/pipeline: '{{"name":"docker-build-oci-ta","bundle":"latest"}}'
    git-provider: github
    git-provider-url: https://github.com
  name: {comp.name_base}-{v}
  namespace: theforeman-org-tenant
spec:
  application: {versioned_app}
  componentName: {comp.name_base}-{v}
  containerImage: {comp.staging_image}
  source:
    git:
      context: {comp.context}
      dockerfileUrl: {comp.dockerfile_url}
      revision: {b}
      url: {comp.repo_url}
""")
    return "".join(parts)


def _project_release_tags(config: ReleaseConfig, project: "_ProjectSpec") -> list[str]:
    """Return the image tags to push for each project's release.

    foreman: Foreman version tags (e.g. ["3.19", "3.19.0-rc1"])
    pulp:    Pulp version + foreman-context tag (e.g. ["3.105", "foreman-3.19"])
    candlepin: Candlepin XY + XYZ + foreman-context tag (e.g. ["4.7", "4.7.4", "foreman-3.19"])

    The foreman-<version> tag is what foremanctl uses to find the correct
    versioned candlepin/pulp images when deploying a specific Foreman release.
    """
    if project.app_name == "pulp":
        return [config.pulp_version, config.foreman_tag]
    if project.app_name == "candlepin":
        return [config.candlepin_version, config.candlepin_version_xyz, config.foreman_tag]
    return list(config.release_tags)


def _releaseplan_kustomization_content(config: ReleaseConfig, project: "_ProjectSpec") -> str:
    v = config.version.replace(".", "-")  # dots invalid in Kubernetes names
    tags = _project_release_tags(config, project)
    tag_lines = "\n".join(f'              - "{t}"' for t in tags)

    components_patch_lines: list[str] = []
    for comp in project.components:
        components_patch_lines.append(
            f"          - name: {comp.name_base}-{v}\n"
            f"            repository: {comp.prod_image}\n"
            f"            tags:\n"
            f"{tag_lines}"
        )
    components_value = "\n".join(components_patch_lines)

    single_component_patch = ""
    if project.single_component_mode:
        single_component_patch = """\
      - op: add
        path: /spec/data/mapping/defaultPushOptions
        value:
          singleComponentMode: true
"""

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
{single_component_patch}\
      - op: replace
        path: /spec/application
        value: {project.app_name}-{v}
      - op: replace
        path: /spec/data/mapping/components
        value:
{components_value}
"""


def _insert_resource_entry(content: str, entry: str, path: "Path | None" = None) -> str:
    """Insert '  - entry/' after the resources: block (after last existing entry)."""
    entry_line = f"  - {entry}/"
    match = _RESOURCES_BLOCK_RE.search(content)
    if match is None:
        location = str(path) if path is not None else "<unknown>"
        raise RuntimeError(
            f"Cannot insert resource: no resources: block found in {location}. "
            "Manual edit required."
        )
    insert_pos = match.end()
    return content[:insert_pos] + f"{entry_line}\n" + content[insert_pos:]


def _update_parent_kustomization(kustomization_path: Path, version: str, dry_run: bool) -> None:
    """Idempotently add '  - {version}/' to the resources list in kustomization_path."""
    if dry_run:
        print(f"[dry-run] Would update {kustomization_path}: add {version!r} to resources")
        return
    entry_line = f"  - {version}/"
    content = kustomization_path.read_text()
    if entry_line in content.splitlines():
        return
    new_content = _insert_resource_entry(content, version, path=kustomization_path)
    kustomization_path.write_text(new_content)
    print(f"  Wrote {kustomization_path}")


def generate_component_overlay(config: ReleaseConfig, project: "_ProjectSpec", tenant_path: Path, dry_run: bool) -> None:
    """Generate components/<VERSION>/ kustomization.yaml, application.yaml, and components.yaml."""
    overlay_dir = tenant_path / "components" / config.version
    if not dry_run:
        overlay_dir.mkdir(parents=True, exist_ok=True)

    _write_file(overlay_dir / "kustomization.yaml", _components_kustomization_content(), dry_run)
    _write_file(overlay_dir / "application.yaml", _application_yaml_content(config, project), dry_run)
    _write_file(overlay_dir / "components.yaml", _components_yaml_content(config, project), dry_run)


def generate_releaseplan_overlay(config: ReleaseConfig, project: "_ProjectSpec", tenant_path: Path, dry_run: bool) -> None:
    """Generate releaseplans/<VERSION>/kustomization.yaml."""
    overlay_dir = tenant_path / "releaseplans" / config.version
    if not dry_run:
        overlay_dir.mkdir(parents=True, exist_ok=True)

    _write_file(overlay_dir / "kustomization.yaml", _releaseplan_kustomization_content(config, project), dry_run)


def update_parent_kustomizations(config: ReleaseConfig, tenant_path: Path, dry_run: bool) -> None:
    """Add <VERSION>/ to components/ and releaseplans/ parent kustomization.yaml files."""
    components_kust = tenant_path / "components" / "kustomization.yaml"
    releaseplans_kust = tenant_path / "releaseplans" / "kustomization.yaml"

    _update_parent_kustomization(components_kust, config.version, dry_run)
    _update_parent_kustomization(releaseplans_kust, config.version, dry_run)
