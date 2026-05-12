# OCI Pipeline File Inventory and Branching Reference

This document is a reference for the `.tekton/` pipeline files across all three
in-scope OCI image repositories. It records the exact shape of the nightly
pipeline files and specifies the diff that must be applied when creating a
versioned Konflux branch. It drives Issues #24, #26, #27, and #28.

---

## Nightly component inventory

Five nightly components exist. Four are in scope for versioned release branching
automation; one is explicitly excluded (see the section below).

| Component | Repository | Default branch | In scope |
|-----------|------------|----------------|----------|
| `foreman-develop` | `theforeman/foreman-oci-images` | `master` | Yes |
| `foreman-proxy-develop` | `theforeman/foreman-oci-images` | `master` | Yes |
| `pulp-develop` | `theforeman/pulpcore-oci-images` | `main` | Yes |
| `candlepin-develop` | `theforeman/candlepin-oci-images` | `master` | Yes |
| `foreman-mcp-server-develop` | `theforeman/foreman-mcp-server` | — | **No** |

---

## foreman-mcp-server scope decision

`foreman-mcp-server-develop` is **explicitly excluded from versioned release
branching automation**.

Rationale: the MCP server has its own release cadence that is independent of the
Foreman RPM release cycle. Its OCI images do not need to be pinned to a specific
Foreman version number, and there is no expectation that a `foreman-mcp-server-3.x`
image would be released in lock-step with a Foreman 3.x release. Automating
versioned branches for this component would create maintenance overhead with no
corresponding value.

The component appears in `docs/release-logic.md` as a nightly component and
remains managed there; it is simply not touched by the branching scripts.

---

## foreman-oci-images

**GitHub repo**: `theforeman/foreman-oci-images`
**Default branch**: `master`

### Files

```
.tekton/
  foreman-develop-push.yaml
  foreman-develop-pull-request.yaml
  foreman-proxy-develop-push.yaml
  foreman-proxy-develop-pull-request.yaml
```

### foreman-develop

| Field | Value |
|-------|-------|
| `metadata.name` | `foreman-develop-on-push` / `foreman-develop-on-pull-request` |
| `appstudio.openshift.io/component` | `foreman-develop` |
| `taskRunTemplate.serviceAccountName` | `build-pipeline-foreman-develop` |
| `output-image` (push) | `quay.io/foreman/foreman-stage:{{revision}}` |
| `output-image` (PR) | `quay.io/foreman/foreman-stage:on-pr-{{revision}}` |
| `path-context` | `images/foreman` |
| `dockerfile` | `Containerfile` |
| Containerfile path | `images/foreman/Containerfile` |
| CEL `target_branch` | `master` |
| CEL `pathChanged` globs | `images/foreman/***`, `.tekton/foreman-develop-{push,pull-request}.yaml` ¹ |
| `buildah-oci-ta` bundle | `quay.io/foreman/tekton-catalog/task-buildah-oci-ta@sha256:4b16776e9028dc9d51e30cd77e832ce9b4b7a400851ede070f84e780bb20de63` |

> ¹ The `{push,pull-request}` shorthand represents two separate CEL expressions: the push pipeline references only its own file (`.tekton/foreman-develop-push.yaml`), and the pull-request pipeline references only `.tekton/foreman-develop-pull-request.yaml`. The same convention applies to all components throughout this document.

**Containerfile version build args** (`images/foreman/Containerfile`):

```dockerfile
ARG FOREMAN_VERSION=nightly
ARG KATELLO_VERSION=nightly
```

### foreman-proxy-develop

| Field | Value |
|-------|-------|
| `metadata.name` | `foreman-proxy-develop-on-push` / `foreman-proxy-develop-on-pull-request` |
| `appstudio.openshift.io/component` | `foreman-proxy-develop` |
| `taskRunTemplate.serviceAccountName` | `build-pipeline-foreman-proxy-develop` |
| `output-image` (push) | `quay.io/foreman/foreman-proxy-stage:{{revision}}` |
| `output-image` (PR) | `quay.io/foreman/foreman-proxy-stage:on-pr-{{revision}}` |
| `path-context` | `images/foreman-proxy` |
| `dockerfile` | `Containerfile` |
| Containerfile path | `images/foreman-proxy/Containerfile` |
| CEL `target_branch` | `master` |
| CEL `pathChanged` globs | `images/foreman-proxy/***`, `.tekton/foreman-proxy-develop-{push,pull-request}.yaml` |
| `buildah-oci-ta` bundle | `quay.io/foreman/tekton-catalog/task-buildah-oci-ta@sha256:4b16776e9028dc9d51e30cd77e832ce9b4b7a400851ede070f84e780bb20de63` |

**Containerfile version build args** (`images/foreman-proxy/Containerfile`):

```dockerfile
ARG FOREMAN_VERSION=nightly
ARG KATELLO_VERSION=nightly
```

---

## pulpcore-oci-images

**GitHub repo**: `theforeman/pulpcore-oci-images`
**Default branch**: `main`

### Files

```
.tekton/
  pulp-develop-push.yaml
  pulp-develop-pull-request.yaml
```

### pulp-develop

| Field | Value |
|-------|-------|
| `metadata.name` | `pulp-develop-on-push` / `pulp-develop-on-pull-request` |
| `appstudio.openshift.io/component` | `pulp-develop` |
| `taskRunTemplate.serviceAccountName` | `build-pipeline-pulp-develop` |
| `output-image` (push) | `quay.io/foreman/pulp-stage:{{revision}}` |
| `output-image` (PR) | `quay.io/foreman/pulp-stage:on-pr-{{revision}}` |
| `path-context` | `images/pulp` |
| `dockerfile` | `images/pulp/Containerfile` |
| Containerfile path | `images/pulp/Containerfile` |
| CEL `target_branch` | `main` |
| CEL `pathChanged` globs | `images/pulp/***`, `.tekton/pulp-develop-{push,pull-request}.yaml`, `images/pulp/Containerfile` |
| `buildah-oci-ta` bundle | `quay.io/konflux-ci/tekton-catalog/task-buildah-oci-ta:0.9@sha256:681d9f65a7f50cb260ee576ccab551e11d63c549f1e1ef3d201da3c112855bd6` |

**Containerfile version build args** (`images/pulp/Containerfile`):

```dockerfile
ARG VERSION=nightly
```

Note: `pulpcore-oci-images` uses `main` as its default branch, unlike the other
two repos which use `master`. The CEL expression must reflect this.

---

## candlepin-oci-images

**GitHub repo**: `theforeman/candlepin-oci-images`
**Default branch**: `master`

### Files

```
.tekton/
  candlepin-develop-push.yaml
  candlepin-develop-pull-request.yaml
```

### candlepin-develop

| Field | Value |
|-------|-------|
| `metadata.name` | `candlepin-develop-on-push` / `candlepin-develop-on-pull-request` |
| `appstudio.openshift.io/component` | `candlepin-develop` |
| `taskRunTemplate.serviceAccountName` | `build-pipeline-candlepin-develop` |
| `output-image` (push) | `quay.io/foreman/candlepin-stage:{{revision}}` |
| `output-image` (PR) | `quay.io/foreman/candlepin-stage:on-pr-{{revision}}` |
| `path-context` | `images/candlepin` |
| `dockerfile` | `Containerfile` |
| Containerfile path | `images/candlepin/Containerfile` |
| CEL `target_branch` | `master` |
| CEL `pathChanged` globs | `images/candlepin/***`, `.tekton/candlepin-develop-{push,pull-request}.yaml` |
| `buildah-oci-ta` bundle | `quay.io/konflux-ci/tekton-catalog/task-buildah-oci-ta:0.9@sha256:681d9f65a7f50cb260ee576ccab551e11d63c549f1e1ef3d201da3c112855bd6` |

**Containerfile version build args** (`images/candlepin/Containerfile`):

```dockerfile
ARG VERSION=4.7
ARG VERSION_XYZ=4.7.4
```

Note: unlike foreman and pulp, the Candlepin Containerfile does **not** default
`VERSION` to `nightly`. The nightly build relies on the Konflux pipeline passing
the correct version build arg at build time.

---

## Image tag flow

For every component, the push pipeline builds two image references:

1. **Staging tag** (produced by `build-image-index`):
   `quay.io/foreman/<component>-stage:{{revision}}`
   This is an internal Konflux staging image used as input to the release pipeline.

2. **Nightly tag** (applied by the Konflux `push-to-external-registry` ReleasePlan):
   `quay.io/theforeman/<component>:nightly`
   This is the publicly consumed image.

The PR pipeline tags the staging image as `on-pr-{{revision}}` (commit SHA) and sets
`image-expires-after: 5d` so ephemeral PR images are cleaned up automatically.
The pull request number appears only in pipeline annotation metadata, not in the image tag.

---

## Versioned branch naming convention

When a new Foreman version (e.g., `3.19`) is released, a versioned branch is
created in each OCI image repository. The branch follows the pattern:

```
konflux-foreman-<VERSION>
```

Examples: `konflux-foreman-3.19`, `konflux-foreman-3.20`.

The Konflux Component name for the versioned build follows the pattern:

```
<image>-<VERSION>
```

Examples: `foreman-3.19`, `foreman-proxy-3.19`, `pulp-3.19`, `candlepin-3.19`.

---

## Exact diff specification: nightly to versioned branch

The following fields change when the nightly `.tekton` files are transformed into
versioned branch files. All other content (task bundles, workspaces, pipeline
parameters, SAST tasks, etc.) remains identical.

Using `foreman` component and version `3.19` as the canonical example; the same
pattern applies to `foreman-proxy`, `pulp`, and `candlepin` with their respective
image and service-account names.

### Push pipeline (`foreman-develop-push.yaml` → `foreman-3.19-push.yaml`)

```diff
-    pipelinesascode.tekton.dev/on-cel-expression: event == "push" && target_branch
-      == "master" && ( "images/foreman/***".pathChanged() || ".tekton/foreman-develop-push.yaml".pathChanged()
-      )
+    pipelinesascode.tekton.dev/on-cel-expression: event == "push" && target_branch
+      == "konflux-foreman-3.19" && ( "images/foreman/***".pathChanged() || ".tekton/foreman-3.19-push.yaml".pathChanged()
+      )

-    appstudio.openshift.io/component: foreman-develop
+    appstudio.openshift.io/component: foreman-3.19

-  name: foreman-develop-on-push
+  name: foreman-3.19-on-push

-  - name: output-image
-    value: quay.io/foreman/foreman-stage:{{revision}}
+  - name: output-image
+    value: quay.io/foreman/foreman-stage:{{revision}}   # unchanged; staging tag is always {{revision}}

-  taskRunTemplate:
-    serviceAccountName: build-pipeline-foreman-develop
+  taskRunTemplate:
+    serviceAccountName: build-pipeline-foreman-3.19
```

**Build args** — the Containerfile `ARG` defaults are overridden at the pipeline
level via the `build-args` parameter:

```diff
+  - name: build-args
+    value:
+    - FOREMAN_VERSION=3.19
+    - KATELLO_VERSION=4.15   # the Katello version paired with Foreman 3.19
```

For `pulp-develop` the build arg becomes:

```diff
+  - name: build-args
+    value:
+    - VERSION=3.19
```

For `candlepin-develop` the build args become:

```diff
+  - name: build-args
+    value:
+    - VERSION=4.7
+    - VERSION_XYZ=4.7.4
```

Note: the Candlepin version is not derived from the Foreman version; it must be
looked up separately for each release.

### PR pipeline (`foreman-develop-pull-request.yaml` → `foreman-3.19-pull-request.yaml`)

The same substitutions apply as for the push pipeline, plus:

```diff
-    pipelinesascode.tekton.dev/on-cel-expression: event == "pull_request" && target_branch
-      == "master" && ( "images/foreman/***".pathChanged() || ".tekton/foreman-develop-pull-request.yaml".pathChanged()
-      )
+    pipelinesascode.tekton.dev/on-cel-expression: event == "pull_request" && target_branch
+      == "konflux-foreman-3.19" && ( "images/foreman/***".pathChanged() || ".tekton/foreman-3.19-pull-request.yaml".pathChanged()
+      )

-  - name: output-image
-    value: quay.io/foreman/foreman-stage:on-pr-{{revision}}
+  - name: output-image
+    value: quay.io/foreman/foreman-stage:on-pr-{{revision}}   # unchanged

-  name: foreman-develop-on-pull-request
+  name: foreman-3.19-on-pull-request
```

### Summary of changed fields per file

| Field | Nightly value | Versioned value (example: 3.19) |
|-------|---------------|---------------------------------|
| `metadata.name` | `foreman-develop-on-push` | `foreman-3.19-on-push` |
| `appstudio.openshift.io/component` | `foreman-develop` | `foreman-3.19` |
| CEL `target_branch` | `master` (or `main` for pulp) | `konflux-foreman-3.19` |
| CEL `.tekton` file reference | `foreman-develop-push.yaml` | `foreman-3.19-push.yaml` |
| `taskRunTemplate.serviceAccountName` | `build-pipeline-foreman-develop` | `build-pipeline-foreman-3.19` |
| `build-args` | _(not set; uses Containerfile defaults)_ | `FOREMAN_VERSION=3.19` (and `KATELLO_VERSION`) |
| `output-image` staging tag | `quay.io/foreman/foreman-stage:{{revision}}` | `quay.io/foreman/foreman-stage:{{revision}}` (unchanged) |

The `output-image` staging tag does **not** change — it always uses `{{revision}}`
as the tag. The public tag (`nightly` vs `3.19`) is applied by the Konflux
release pipeline, not by the `.tekton` file.

---

## Pipeline bundle schema note

The `.tekton` files pin every Tekton task bundle by digest
(`quay.io/..../task-foo@sha256:...`). The custom `buildah-oci-ta` task used by
this project is published at:

```
quay.io/foreman/tekton-catalog/task-buildah-oci-ta@sha256:<digest>
```

> **Note:** As of this writing, only `foreman-develop` and `foreman-proxy-develop`
> reference the custom bundle. `pulp-develop` and `candlepin-develop` still
> reference the upstream `quay.io/konflux-ci/tekton-catalog/task-buildah-oci-ta`
> bundle. Migrating all repos to the custom bundle is tracked in issue #40.

When the upstream `pipeline-push-to-external-registry` bundle schema changes
(new parameters, renamed tasks, etc.):

1. Update the digest in the Jinja2 template at
   `hack/branch-release/templates/` in this repository (planned infrastructure,
   to be created by issues #26–#28).
2. Regenerate all versioned `.tekton` files from the updated template.
3. Open a PR to each affected OCI image repository to land the updated files on
   the versioned branches.

Do not update individual versioned files by hand — always regenerate from the
template to keep all branches consistent.
