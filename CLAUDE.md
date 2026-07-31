# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository purpose

`theforeman-rel-eng-konflux` is the release engineering home for [The Foreman](https://theforeman.org/) project's [Konflux](https://konflux-ci.fedoraproject.org/) CI/CD artifacts. It holds:

- Custom Tekton tasks and pipelines published as OCI bundles to `quay.io/foreman/tekton-catalog`
- (Planned) branching automation scripts for versioned OCI image releases (`hack/branch-release/`)

The RPM-release equivalent is https://github.com/theforeman/theforeman-rel-eng — the `branch_project`, `wait_packaging`, and `settings` scripts there define the pattern being mirrored here for container images.

All work toward Konflux OCI image branching automation is tracked under the **"Konflux OCI Image Branching Automation"** milestone: https://github.com/theforeman/theforeman-rel-eng-konflux/milestone/1

## Repos this automation touches

| Repo | Platform | Purpose |
|---|---|---|
| https://github.com/theforeman/theforeman-rel-eng-konflux | GitHub | **This repo** — scripts, CLAUDE.md, release settings |
| https://github.com/theforeman/foreman-oci-images | GitHub | Foreman + Foreman Proxy container images |
| https://github.com/theforeman/pulp-oci-images | GitHub | Pulp container images |
| https://github.com/theforeman/candlepin-oci-images | GitHub | Candlepin container images |
| https://gitlab.com/fedora/infrastructure/konflux/tenants-config/-/tree/main/clusters/kflux-fedora-01/tenants/theforeman-org-tenant | GitLab | Konflux resource definitions (Application, Component, ReleasePlan) |

## Directory layout

```
tekton-catalog/
  hack/push-bundles.sh          # local helper for testing bundle builds
  pipelines/push-to-external-registry/
    kustomization.yaml          # pulls upstream pipeline; applies patch.yaml
    patch.yaml                  # JSON 6902 patches (removes verify-access-to-resources,
                                # makes RPA/RSC optional, sets ociStorage default)
  tasks/
    buildah-oci-ta/
      kustomization.yaml        # pulls upstream task; applies patch.yaml
      patch.yaml                # memory/CPU patches (OOM fixes for large Foreman images)
    collect-data/
      collect-data.yaml         # Foreman fork: makes releasePlanAdmission + releaseServiceConfig optional
    check-non-root-user/
      check-non-root-user.yaml # custom task: fails build if image config runs as root
      kustomization.yaml
docs/
  release-logic.md              # nightly release flow and components
.github/workflows/
  publish-pipeline-bundle.yml   # publishes bundles to quay.io on push to develop
  yamllint.yml                  # runs yamllint . on PRs touching tekton-catalog/**
  kustomize-build.yml           # validates kustomize build on PRs touching tekton-catalog/**
```

**Planned layout** (not yet implemented):

```
hack/branch-release/
  branch_konflux               # orchestrator — run as: hack/branch-release/branch_konflux --version=3.19
  lib/
    config.py                  # reads releases/foreman/VERSION/settings via shlex
    git.py                     # git worktree + branch operations
    tekton.py                  # renders .tekton YAML from Jinja2 templates
    containerfile.py           # patches ARG FOREMAN_VERSION in Containerfiles
    tenants.py                 # generates Component + ReleasePlan YAML
    github.py                  # gh CLI wrapper
    gitlab.py                  # glab CLI wrapper
    rpm_check.py               # polls yum.theforeman.org for RPM availability
    runner.py                  # step runner (interactive / auto / dry-run / resume)
  templates/
    tekton-push.yaml.j2
    tekton-pull-request.yaml.j2
    kustomization-releaseplan.yaml.j2
  tests/
releases/
  foreman/
    3.19/
      settings                 # shell key=value script config (see below — NOT a K8s resource)
```

## Critical distinction: two different `releases/` concepts

Commit `80cac13` removed a `releases/` directory from this repo. That directory held **Kubernetes resource YAML** (ReleasePlan, ReleasePlanAdmission CRDs) that have since moved to tenants-config.

The branching scripts plan to create a **different** `releases/` directory holding **shell-style script configuration files** (plain text, read by Python via `shlex`) — e.g. `releases/foreman/3.19/settings`. These are not Kubernetes resources. Do not confuse them.

### Release settings file format

```bash
VERSION=3.19
BRANCH_NAME=foreman-3.19
# Default branch is detected dynamically via `gh repo view --json defaultBranchRef`
# Do not hardcode master/main here.
OCI_REPOS="theforeman/foreman-oci-images theforeman/pulp-oci-images theforeman/candlepin-oci-images"
RELEASE_TAGS="3.19 3.19.0"
RPM_CHECK_URL=https://yum.theforeman.org/releases/3.19/el9/x86_64/repodata/repomd.xml
RPM_CHECK_TIMEOUT=14400
```

Version format is MAJOR.MINOR only (`3.19` is valid; `3.19.1` or `nightly` are rejected by the scripts).

## Required tools

| Tool | Min version | Verify |
|---|---|---|
| `uv` | ≥ 0.4.0 | `uv --version` |
| `git` | ≥ 2.36 | `git --version` |
| `gh` (GitHub CLI) | any | `gh auth status` |
| `glab` (GitLab CLI) | any | `glab auth status` |
| `yq` | mikefarah build | `yq --version \| grep mikefarah` |
| `jq` | any | `jq --version` |
| `kustomize` | any | `kustomize version` |
| `oc` | any | `oc version` |

**Python execution**: all scripts are run via `uv run` — `uv` manages the Python interpreter (≥ 3.9) and dependencies automatically. No manual `pip install` or virtualenv needed. The only non-stdlib dependency is `jinja2`; declare it in `/// script` inline metadata or a `pyproject.toml` at `hack/branch-release/`.

## Required fork setup

Before running `branch_konflux`, ensure you have:

- **GitHub forks** for: `foreman-oci-images`, `pulp-oci-images`, `candlepin-oci-images`
- **GitLab fork** for: `tenants-config`

### Remote naming convention

Scripts enforce this in preflight and will fail if remotes are wrong:

- `upstream` → the `theforeman/` (or `fedora/`) org remote
- `origin` → your personal fork

## Environment variables

| Variable | Required | Description |
|---|---|---|
| `FOREMAN_VERSION` | yes (or `--version`) | Release version, e.g. `3.19` |
| `GITHUB_USER` | yes | Your GitHub username |
| `GITLAB_USER` | yes | Your GitLab username |
| `WORKTREE_DIR` | no | Override worktree base (default: `/tmp/konflux-branch-<VERSION>`) |

## Script flags

| Flag | Description |
|---|---|
| `--dry-run` | Print actions without making changes |
| `--auto` | Non-interactive; skip all confirmation prompts |
| `--step=NAME` | Resume from a named step: skips all steps before it, then runs that step and all subsequent ones |
| `--skip-rpm-check` | Skip RPM availability gate (useful when RPMs are not yet published) |

## Branching a new release

```bash
# Always dry-run first
uv run hack/branch-release/branch_konflux --version=3.19 --dry-run

# Real run (interactive by default)
uv run hack/branch-release/branch_konflux --version=3.19
```

### Orchestrator step order

1. `preflight` — validates tools, forks, remote names, version format
2. `branch-oci-foreman-oci-images` — creates branch in foreman-oci-images
3. `branch-oci-pulp-oci-images` — creates branch in pulp-oci-images
4. `branch-oci-candlepin-oci-images` — creates branch in candlepin-oci-images
5. `wait-rpms` — polls `RPM_CHECK_URL` until RPMs appear (gates tenants-config MR, not OCI branch creation)
6. `branch-tenants` — opens MR against tenants-config with new Component + ReleasePlan YAML

### wait-rpms timing note

OCI branches can (and should) be created before RPMs exist. The RPM gate (`wait-rpms`) controls only when the **tenants-config MR is merged** — not when OCI branches are created. Use `--skip-rpm-check` to skip this gate during testing.

### Merge sequence

1. Review and merge OCI repo PRs (`foreman-oci-images`, `pulp-oci-images`, `candlepin-oci-images`)
2. Wait for RPMs to appear at `RPM_CHECK_URL` (or skip with `--skip-rpm-check`)
3. Merge the tenants-config MR

## git worktrees

The script clones each OCI repo into a temporary git worktree:

- Path pattern: `/tmp/konflux-branch-<VERSION>/<repo>` (or `$WORKTREE_DIR/<repo>`)
- Cleaned up automatically on success
- Left in place on failure for inspection and manual recovery

Manual cleanup:

```bash
rm -rf /tmp/konflux-branch-3.19/
```

## Recovery

**OCI image branches are permanent** — do not delete them. They are part of the project history and the images they produce are published to production Quay namespaces (`quay.io/foreman/`). A versioned image is reproducible from the same branch at any time.

If a branch was created with wrong `.tekton` files, open a PR against the versioned branch to correct them:

```bash
git checkout foreman-3.19
git checkout -b fix-tekton-foreman-3.19
# edit the wrong file
git commit -m "Fix .tekton pipeline for 3.19"
git push origin fix-tekton-foreman-3.19
gh pr create --base foreman-3.19 --title "Fix .tekton pipeline for 3.19"
```

**Konflux resources are ephemeral** — the Component and ReleasePlan CRs in tenants-config can be freely removed and recreated. To de-register a versioned release from Konflux (e.g., after a bad rollout):

1. Remove the versioned overlay directories from tenants-config:
   ```
   foreman/components/3.19/
   foreman/releaseplans/3.19/
   ```
2. Remove those paths from the parent `kustomization.yaml` files.
3. Merge the MR — ArgoCD reconciles and removes the Component/ReleasePlan CRs.
4. The branch and its images remain intact and can be re-registered later.

See issue #35 for the full rollback runbook.

## Running tests

```bash
uv run pytest hack/branch-release/tests/
```

## Linting and validation

```bash
# YAML lint (required before committing any .yaml/.yml file)
yamllint .

# Validate kustomize renders cleanly
kustomize build tekton-catalog/pipelines/push-to-external-registry/
kustomize build tekton-catalog/tasks/buildah-oci-ta/
```

The `.yamllint` config requires `document-start: present` (`---` at top of every YAML file), consistent indentation, and max 1 blank line between blocks. Line length is disabled.

## How tekton-catalog bundles are published

Bundles are **not** built from this repo's YAML directly — they are assembled by `kustomize build` which fetches upstream YAML at build time and applies local `patch.yaml` overlays. The CI workflow (`publish-pipeline-bundle.yml`) runs on push to `develop` and publishes to `quay.io/foreman/tekton-catalog` with three tags: `<full-version>`, `<minor-version>`, and `latest`.

`tekton-catalog/hack/push-bundles.sh` is the local equivalent for manual testing only.

**When a task bundle is updated:** after a new `task-buildah-oci-ta` bundle is published (triggered by a merge to `develop` that changes `tekton-catalog/tasks/buildah-oci-ta/`), open a follow-up PR to every OCI image repo to update the bundle digest in their `.tekton/` files. Use `skopeo inspect docker://quay.io/foreman/tekton-catalog/task-buildah-oci-ta:0.9 | jq -r .Digest` to get the current digest.

## PR/MR rules

- Never push directly to `develop` or `main` — always open a PR/MR
- No force-push
- No skipping hooks (`--no-verify`)
- `.tekton` pipeline YAML files in upstream OCI repos are managed by Konflux automation, but **must be updated manually** when a custom task bundle changes. When `tekton-catalog/tasks/buildah-oci-ta/` is updated and a new bundle is published, open a follow-up PR to every OCI image repo (`foreman-oci-images`, `pulp-oci-images`, `candlepin-oci-images`, `foreman-mcp-server`) to update the bundle digest. All repos must reference the same custom bundle version (tracked in #40).

## Architecture: how nightly releases work

Konflux Application/Component/ReleasePlan resources live in the tenants-config GitLab repo, not here. Nightly components: `foreman-develop`, `foreman-proxy-develop`, `pulp-develop`, `candlepin-develop`, `foreman-mcp-server-develop`. These build and release automatically via the `push-to-external-registry` pipeline to `quay.io/foreman/` with the `nightly` tag.

The custom `collect-data` task in this repo is a fork of the upstream Konflux task that makes `releasePlanAdmission` and `releaseServiceConfig` optional (defaulting to `""`), allowing releases without a ReleasePlanAdmission CRD.

The `buildah-oci-ta` task patches upstream memory/CPU limits upward because Foreman images are large enough to OOM at upstream defaults (build step needs 16Gi; sbom-syft-generate needs 8Gi).

## External references

- **tenants-config (Foreman)**: https://gitlab.com/fedora/infrastructure/konflux/tenants-config/-/tree/main/clusters/kflux-fedora-01/tenants/theforeman-org-tenant
- **bootc-tenant pattern** (versioned release blueprint): https://gitlab.com/fedora/infrastructure/konflux/tenants-config/-/tree/main/clusters/kflux-fedora-01/tenants/bootc-tenant
- **Konflux docs**: https://konflux-ci.dev/docs/
- **theforeman-rel-eng** (RPM equivalent): https://github.com/theforeman/theforeman-rel-eng
- **Milestone**: https://github.com/theforeman/theforeman-rel-eng-konflux/milestone/1
