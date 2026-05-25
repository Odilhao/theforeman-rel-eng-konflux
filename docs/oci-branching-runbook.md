---
# Manual OCI Branching Runbook

This runbook covers every step needed to branch a new Foreman release across
all OCI image repositories and register the versioned components in Konflux —
done entirely by hand, with no automation scripts required.

Follow the steps in order. Each step notes the equivalent `branch_konflux`
command so you can resume with the orchestrator at any point.

**Audience:** release engineers performing a versioned Foreman branch (e.g., `3.19`).

**Substitute `3.19` with your actual version throughout.** The branch name
follows the pattern `foreman-<VERSION>` (e.g., `foreman-3.19`).

---

## Contents

- [Prerequisites](#prerequisites)
- [Phase 0 — Pre-flight checks](#phase-0--pre-flight-checks)
- [Phase 1 — Branch foreman-oci-images](#phase-1--branch-foreman-oci-images)
- [Phase 2 — Branch pulp-oci-images](#phase-2--branch-pulp-oci-images)
- [Phase 3 — Branch candlepin-oci-images](#phase-3--branch-candlepin-oci-images)
- [Phase 4 — Wait for RPM availability](#phase-4--wait-for-rpm-availability)
- [Phase 5 — Generate tenants-config overlays](#phase-5--generate-tenants-config-overlays)
- [Phase 6 — Fix Konflux-generated .tekton files](#phase-6--fix-konflux-generated-tekton-files)
- [Phase 7 — Merge sequence](#phase-7--merge-sequence)
- [Phase 8 — Verify in Konflux UI](#phase-8--verify-in-konflux-ui)
- [Troubleshooting](#troubleshooting)

---

## Prerequisites

### Required tools

Verify each tool is installed before starting. The `preflight` step checks
these automatically.

| Tool | Verify command |
|------|----------------|
| `git` (≥ 2.36) | `git --version` |
| `gh` (GitHub CLI) | `gh auth status` |
| `glab` (GitLab CLI) | `glab auth status` |
| `yq` (mikefarah build) | `yq --version \| grep mikefarah` |
| `jq` | `jq --version` |
| `kustomize` | `kustomize version` |
| `oc` | `oc version` |
| `uv` (≥ 0.4.0) | `uv --version` |

All `gh` and `glab` commands require active authentication:

```bash
gh auth status
GLAB_HOST=gitlab.com GITLAB_HOST=gitlab.com glab auth status
```

**Important:** glab does not support `--hostname` on all subcommands. Always
pass the host via environment variables instead:

```bash
export GLAB_HOST=gitlab.com
export GITLAB_HOST=gitlab.com   # overrides any shell-level GITLAB_HOST (e.g. internal Red Hat instance)
```

If your shell sets `GITLAB_TOKEN` to an old or internal-instance token, unset it
so glab uses its stored credentials:

```bash
unset GITLAB_TOKEN
```

### Required forks

You must own personal forks of all four upstream repositories before starting.

**GitHub forks** (fork from the `theforeman/` org):

- `theforeman/foreman-oci-images`
- `theforeman/pulp-oci-images`
- `theforeman/candlepin-oci-images`

**GitLab fork** (fork from `fedora/infrastructure/konflux/`):

- `fedora/infrastructure/konflux/tenants-config`

Verify each GitHub fork exists:

```bash
gh repo view $GITHUB_USER/foreman-oci-images --json name
gh repo view $GITHUB_USER/pulp-oci-images --json name
gh repo view $GITHUB_USER/candlepin-oci-images --json name
```

Verify the GitLab fork (use full URL — short form returns 404):

```bash
GLAB_HOST=gitlab.com GITLAB_HOST=gitlab.com \
  glab repo view https://gitlab.com/$GITLAB_USER/tenants-config
```

### Remote naming convention

All scripts enforce the following remote naming. Verify your local remotes match
before starting.

| Remote | Points to |
|--------|-----------|
| `upstream` | The `theforeman/` (or `fedora/`) org repository |
| `origin` | Your personal fork |

**SSH is required for pushing to upstream.** Clone via HTTPS (public repos,
no auth needed) but use SSH for push:

```bash
# After cloning with --origin upstream, set the push URL to SSH:
git remote set-url --push upstream git@github.com:theforeman/<repo>.git
```

Or configure `GITHUB_UPSTREAM_URL_BASE=git@github.com:theforeman` in
`hack/branch-release/settings.local` to have the script handle this automatically.

### Settings file

Create the release settings file at `releases/foreman/3.19/settings` (adjust
path for your version):

```bash
mkdir -p releases/foreman/3.19
```

Populate it with the following key=value pairs:

```bash
# releases/foreman/3.19/settings
VERSION=3.19
BRANCH_NAME=foreman-3.19
OCI_REPOS="theforeman/foreman-oci-images theforeman/pulp-oci-images theforeman/candlepin-oci-images"
RELEASE_TAGS="3.19 3.19.0-rc1"
RPM_CHECK_URL=https://yum.theforeman.org/releases/3.19/el9/x86_64/repodata/repomd.xml
RPM_CHECK_TIMEOUT=14400
KATELLO_VERSION=<katello-version>       # e.g. 4.21
PULP_VERSION=<pulp-version>             # e.g. 3.105
CANDLEPIN_VERSION=<candlepin-version>   # e.g. 4.7
CANDLEPIN_VERSION_XYZ=<candlepin-xyz>   # e.g. 4.7.4
```

Replace the angle-bracket placeholders with the actual companion release
versions. Version format must be `MAJOR.MINOR` (e.g., `3.19`); `MAJOR.MINOR.PATCH`
and `nightly` are rejected.

### Environment variables

Run the following block once from the **root of the `theforeman-rel-eng-konflux`
repo** before starting any phase. All later steps assume these variables are set.

```bash
export GITHUB_USER=<your-github-username>
export GITLAB_USER=<your-gitlab-username>
export GLAB_HOST=gitlab.com
export GITLAB_HOST=gitlab.com
unset GITLAB_TOKEN   # prevent stale token from overriding glab stored credentials
export VERSION=3.19
export BRANCH_NAME=foreman-3.19

# Kubernetes-safe version — dots replaced with hyphens (required for resource names)
export VERSION_K8S=${VERSION//./-}   # e.g. "3-19"

# Source the release settings file — sets KATELLO_VERSION, PULP_VERSION,
# CANDLEPIN_VERSION, CANDLEPIN_VERSION_XYZ, RELEASE_TAGS, RPM_CHECK_URL, etc.
source releases/foreman/$VERSION/settings

# Foreman-prefixed tag used by foremanctl for pulp/candlepin image lookups
export FOREMAN_TAG=foreman-$VERSION   # e.g. "foreman-3.19"

export WORKTREE_DIR=/tmp   # optional — override if /tmp is too small or restricted
```

---

## Phase 0 — Pre-flight checks

> *Or run: `uv run hack/branch-release/branch_konflux --version=3.19 --step=preflight`*

- [ ] **0.1** Verify all required tools are installed and in `$PATH`:

  ```bash
  for tool in git gh glab yq jq kustomize oc uv; do
    if command -v "$tool" &>/dev/null; then
      echo "[ok] $tool"
    else
      echo "[MISSING] $tool"
    fi
  done
  ```

  **Expected output:** `[ok]` for every tool. Stop and install any missing tools
  before continuing.

- [ ] **0.2** Confirm GitHub CLI is authenticated:

  ```bash
  gh auth status
  ```

  **Expected output:** `Logged in to github.com as <username>`.

- [ ] **0.3** Confirm GitLab CLI is authenticated for gitlab.com:

  ```bash
  GLAB_HOST=gitlab.com GITLAB_HOST=gitlab.com glab auth status
  ```

  **Expected output:** `You are logged in to gitlab.com as <username>`.

- [ ] **0.4** Verify GitHub forks exist:

  ```bash
  gh repo view $GITHUB_USER/foreman-oci-images --json name -q .name
  gh repo view $GITHUB_USER/pulp-oci-images --json name -q .name
  gh repo view $GITHUB_USER/candlepin-oci-images --json name -q .name
  ```

  **Expected output:** repository names (`foreman-oci-images`, etc.). A 404 means the fork is missing — create it from the GitHub UI before continuing.

- [ ] **0.5** Verify GitLab fork exists (use the full URL form):

  ```bash
  GLAB_HOST=gitlab.com GITLAB_HOST=gitlab.com \
    glab repo view https://gitlab.com/$GITLAB_USER/tenants-config
  ```

  **Expected output:** repository details. If it fails, create the fork at
  https://gitlab.com/fedora/infrastructure/konflux/tenants-config.

- [ ] **0.6** Check for an existing versioned Konflux component (warn only):

  ```bash
  for c in foreman foreman-proxy pulp candlepin; do
    oc get component ${c}-${VERSION_K8S} -n theforeman-org-tenant 2>/dev/null \
      && echo "EXISTS: ${c}-${VERSION_K8S}" || true
  done
  ```

  **Expected output for a fresh branch:** no output. If any component already
  exists, the `branch-tenants` phase may produce duplicate resources; review
  carefully before proceeding.

- [ ] **0.7** Confirm the settings file exists and is parseable:

  ```bash
  cat releases/foreman/$VERSION/settings
  ```

  Confirm all required fields are present: `VERSION`, `BRANCH_NAME`,
  `KATELLO_VERSION`, `PULP_VERSION`, `CANDLEPIN_VERSION`, `CANDLEPIN_VERSION_XYZ`.

---

## Phase 1 — Branch foreman-oci-images

> *Or run: `uv run hack/branch-release/branch_konflux --version=3.19 --step=branch-oci-foreman-oci-images`*

**Precondition:** nightly CI on `master` must be passing before cutting the
release branch. Confirm at the [Konflux console](https://konflux.fedoraproject.org)
or in the GitHub status checks on `master`. Do not proceed with a broken nightly.

- [ ] **1.1** Detect the default branch:

  ```bash
  DEFAULT_BRANCH=$(gh repo view theforeman/foreman-oci-images --json defaultBranchRef -q .defaultBranchRef.name)
  echo "Default branch: $DEFAULT_BRANCH"
  ```

  **Expected output:** `Default branch: master`

- [ ] **1.2** Clone into a temporary worktree with both remotes:

  ```bash
  mkdir -p $WORKTREE_DIR/konflux-branch-$VERSION
  cd $WORKTREE_DIR/konflux-branch-$VERSION
  git clone https://github.com/theforeman/foreman-oci-images.git --origin upstream
  cd foreman-oci-images
  git remote add origin git@github.com:$GITHUB_USER/foreman-oci-images.git
  # Set upstream push URL to SSH (HTTPS clone works without auth; push requires SSH key)
  git remote set-url --push upstream git@github.com:theforeman/foreman-oci-images.git
  ```

  **Verify remotes:**

  ```bash
  git remote -v
  ```

  You should see `upstream` pointing to `theforeman/` (fetch: HTTPS, push: SSH)
  and `origin` pointing to your fork (SSH).

- [ ] **1.3** Check whether the branch already exists on upstream:

  ```bash
  git ls-remote upstream refs/heads/$BRANCH_NAME
  ```

  **Expected output for a fresh branch:** empty (no output). If the branch
  already exists, do **not** delete it — OCI image branches are permanent.
  See the [Recovery section in CLAUDE.md](../CLAUDE.md#recovery) for the
  correct procedure.

- [ ] **1.4** Create the release branch:

  ```bash
  git checkout -b $BRANCH_NAME upstream/$DEFAULT_BRANCH
  ```

  **Expected output:** `Switched to a new branch 'foreman-3.19'`

- [ ] **1.5** Push the branch to upstream first (this creates it in the upstream repo
  so Konflux can reference it before the PR is merged):

  ```bash
  git push upstream $BRANCH_NAME
  ```

  **Expected output:** `* [new branch] foreman-3.19 -> foreman-3.19`

- [ ] **1.6** Patch Containerfile ARG values to pin release versions.

  Patch `images/foreman/Containerfile`:

  ```bash
  sed -i "s|^ARG FOREMAN_VERSION=.*|ARG FOREMAN_VERSION=$VERSION|" images/foreman/Containerfile
  sed -i "s|^ARG KATELLO_VERSION=.*|ARG KATELLO_VERSION=$KATELLO_VERSION|" images/foreman/Containerfile
  ```

  Patch `images/foreman-proxy/Containerfile` (both FOREMAN_VERSION and KATELLO_VERSION):

  ```bash
  sed -i "s|^ARG FOREMAN_VERSION=.*|ARG FOREMAN_VERSION=$VERSION|" images/foreman-proxy/Containerfile
  sed -i "s|^ARG KATELLO_VERSION=.*|ARG KATELLO_VERSION=$KATELLO_VERSION|" images/foreman-proxy/Containerfile
  ```

  **Verify the patches:**

  ```bash
  grep "^ARG FOREMAN_VERSION\|^ARG KATELLO_VERSION" images/foreman/Containerfile
  grep "^ARG FOREMAN_VERSION\|^ARG KATELLO_VERSION" images/foreman-proxy/Containerfile
  ```

  **Expected output (both files):**

  ```
  ARG FOREMAN_VERSION=3.19
  ARG KATELLO_VERSION=<katello-version>
  ```

- [ ] **1.7** Patch the Makefile version variables:

  ```bash
  sed -i "s|^FOREMAN_XY_TAG=.*|FOREMAN_XY_TAG=$VERSION|" Makefile
  sed -i "s|^FOREMAN_XYZ_TAG=.*|FOREMAN_XYZ_TAG=${RELEASE_TAGS##* }|" Makefile   # last tag in RELEASE_TAGS
  sed -i "s|^KATELLO_VERSION=.*|KATELLO_VERSION=$KATELLO_VERSION|" Makefile
  ```

  **Verify:**

  ```bash
  grep "^FOREMAN_XY_TAG\|^FOREMAN_XYZ_TAG\|^KATELLO_VERSION" Makefile
  ```

- [ ] **1.8** Patch the GitHub Actions workflow `IMAGE_TAG` (controls image tag used
  in integration tests — without this, tests build with nightly packages):

  ```bash
  sed -i "s|IMAGE_TAG: nightly|IMAGE_TAG: \"$VERSION\"|" .github/workflows/integration.yml
  ```

  **Verify:**

  ```bash
  grep "IMAGE_TAG" .github/workflows/integration.yml
  ```

  **Expected output:** `  IMAGE_TAG: "3.19"`

- [ ] **1.9** Commit all patches in one commit:

  ```bash
  git add images/foreman/Containerfile images/foreman-proxy/Containerfile \
          Makefile .github/workflows/integration.yml
  git commit -m "Branch $BRANCH_NAME: patch Containerfile versions, Makefile tags, and workflow"
  ```

- [ ] **1.10** Push the patched branch to your fork:

  ```bash
  git push origin $BRANCH_NAME
  ```

- [ ] **1.11** Open a draft PR targeting the versioned branch in upstream
  (not the default branch — the PR is for reviewing the version-specific patches):

  ```bash
  gh pr create \
    --repo theforeman/foreman-oci-images \
    --base $BRANCH_NAME \
    --head $GITHUB_USER:$BRANCH_NAME \
    --title "Branch: $BRANCH_NAME" \
    --body "Branch \`$BRANCH_NAME\` for Foreman $VERSION release.

  This PR patches Containerfile ARG values, Makefile tags, and the integration
  workflow IMAGE_TAG to pin the release version.

  Part of the Foreman $VERSION Konflux branching process." \
    --draft
  ```

  **Expected output:** a GitHub PR URL. Save it.

---

## Phase 2 — Branch pulp-oci-images

> *Or run: `uv run hack/branch-release/branch_konflux --version=3.19 --step=branch-oci-pulp-oci-images`*

**Precondition:** nightly CI on `main` must be passing.

- [ ] **2.1** Detect the default branch:

  ```bash
  DEFAULT_BRANCH_PULP=$(gh repo view theforeman/pulp-oci-images --json defaultBranchRef -q .defaultBranchRef.name)
  echo "Default branch: $DEFAULT_BRANCH_PULP"
  ```

  **Expected output:** `Default branch: main`

- [ ] **2.2** Clone into a temporary worktree:

  ```bash
  cd $WORKTREE_DIR/konflux-branch-$VERSION
  git clone https://github.com/theforeman/pulp-oci-images.git --origin upstream
  cd pulp-oci-images
  git remote add origin git@github.com:$GITHUB_USER/pulp-oci-images.git
  git remote set-url --push upstream git@github.com:theforeman/pulp-oci-images.git
  ```

- [ ] **2.3** Check for existing branch:

  ```bash
  git ls-remote upstream refs/heads/$BRANCH_NAME
  ```

  **Expected output for a fresh branch:** empty.

- [ ] **2.4** Create the release branch:

  ```bash
  git checkout -b $BRANCH_NAME upstream/$DEFAULT_BRANCH_PULP
  ```

- [ ] **2.5** Push to upstream (creates the branch Konflux will build from):

  ```bash
  git push upstream $BRANCH_NAME
  ```

- [ ] **2.6** Patch `images/pulp/Containerfile`. The Pulp Containerfile uses
  `ARG VERSION=nightly` which must be pinned to the Pulp version for this release
  (`PULP_VERSION` was loaded by `source releases/foreman/$VERSION/settings`):

  ```bash
  sed -i "s|^ARG VERSION=.*|ARG VERSION=$PULP_VERSION|" images/pulp/Containerfile
  ```

  **Verify:**

  ```bash
  grep "^ARG VERSION" images/pulp/Containerfile
  ```

  **Expected output:** `ARG VERSION=3.105`

- [ ] **2.7** Patch the Makefile version variables:

  ```bash
  sed -i "s|^PROJECT_XY_TAG=.*|PROJECT_XY_TAG=$PULP_VERSION|" Makefile
  sed -i "s|^PROJECT_XYZ_TAG=.*|PROJECT_XYZ_TAG=$PULP_VERSION|" Makefile
  sed -i "s|^FOREMAN_XY_TAG=.*|FOREMAN_XY_TAG=$FOREMAN_TAG|" Makefile
  sed -i "s|^FOREMAN_XYZ_TAG=.*|FOREMAN_XYZ_TAG=$FOREMAN_TAG|" Makefile
  ```

  **Verify:**

  ```bash
  grep "^PROJECT_XY_TAG\|^PROJECT_XYZ_TAG\|^FOREMAN_XY_TAG\|^FOREMAN_XYZ_TAG" Makefile
  ```

- [ ] **2.8** Commit all patches:

  ```bash
  git add images/pulp/Containerfile Makefile
  git commit -m "Branch $BRANCH_NAME: patch Containerfile VERSION and Makefile tags"
  ```

- [ ] **2.9** Push to fork:

  ```bash
  git push origin $BRANCH_NAME
  ```

- [ ] **2.10** Open a draft PR targeting the versioned branch:

  ```bash
  gh pr create \
    --repo theforeman/pulp-oci-images \
    --base $BRANCH_NAME \
    --head $GITHUB_USER:$BRANCH_NAME \
    --title "Branch: $BRANCH_NAME" \
    --body "Branch \`$BRANCH_NAME\` for Foreman $VERSION release.

  Pins Pulp VERSION to $PULP_VERSION and updates Makefile image tags.

  Part of the Foreman $VERSION Konflux branching process." \
    --draft
  ```

---

## Phase 3 — Branch candlepin-oci-images

> *Or run: `uv run hack/branch-release/branch_konflux --version=3.19 --step=branch-oci-candlepin-oci-images`*

**Precondition:** nightly CI on `master` must be passing.

- [ ] **3.1** Detect the default branch:

  ```bash
  DEFAULT_BRANCH_CP=$(gh repo view theforeman/candlepin-oci-images --json defaultBranchRef -q .defaultBranchRef.name)
  echo "Default branch: $DEFAULT_BRANCH_CP"
  ```

  **Expected output:** `Default branch: master`

- [ ] **3.2** Clone into a temporary worktree:

  ```bash
  cd $WORKTREE_DIR/konflux-branch-$VERSION
  git clone https://github.com/theforeman/candlepin-oci-images.git --origin upstream
  cd candlepin-oci-images
  git remote add origin git@github.com:$GITHUB_USER/candlepin-oci-images.git
  git remote set-url --push upstream git@github.com:theforeman/candlepin-oci-images.git
  ```

- [ ] **3.3** Check for existing branch:

  ```bash
  git ls-remote upstream refs/heads/$BRANCH_NAME
  ```

  **Expected output for a fresh branch:** empty.

- [ ] **3.4** Create the release branch and push to upstream:

  ```bash
  git checkout -b $BRANCH_NAME upstream/$DEFAULT_BRANCH_CP
  git push upstream $BRANCH_NAME
  ```

- [ ] **3.5** Patch `images/candlepin/Containerfile`. The candlepin Containerfile
  uses `ARG VERSION` and `ARG VERSION_XYZ` (not `CANDLEPIN_VERSION`):

  ```bash
  sed -i "s|^ARG VERSION=.*|ARG VERSION=$CANDLEPIN_VERSION|" images/candlepin/Containerfile
  sed -i "s|^ARG VERSION_XYZ=.*|ARG VERSION_XYZ=$CANDLEPIN_VERSION_XYZ|" images/candlepin/Containerfile
  ```

  **Verify:**

  ```bash
  grep "^ARG VERSION" images/candlepin/Containerfile
  ```

  **Expected output:**

  ```
  ARG VERSION=4.7
  ARG VERSION_XYZ=4.7.4
  ```

- [ ] **3.6** Patch the Makefile. Candlepin Makefile tracks both project version tags
  and foreman-context tags:

  ```bash
  sed -i "s|^FOREMAN_XY_TAG=.*|FOREMAN_XY_TAG=$FOREMAN_TAG|" Makefile
  sed -i "s|^FOREMAN_XYZ_TAG=.*|FOREMAN_XYZ_TAG=$FOREMAN_TAG|" Makefile
  ```

  **Note:** `PROJECT_XY_TAG` and `PROJECT_XYZ_TAG` in the candlepin Makefile are
  already derived correctly from the Containerfile ARGs — they do not need to be
  patched separately.

  **Verify:**

  ```bash
  grep "^FOREMAN_XY_TAG\|^FOREMAN_XYZ_TAG" Makefile
  ```

- [ ] **3.7** Commit all patches:

  ```bash
  git add images/candlepin/Containerfile Makefile
  git commit -m "Branch $BRANCH_NAME: patch Containerfile versions and Makefile tags"
  ```

- [ ] **3.8** Push to fork:

  ```bash
  git push origin $BRANCH_NAME
  ```

- [ ] **3.9** Open a draft PR targeting the versioned branch:

  ```bash
  gh pr create \
    --repo theforeman/candlepin-oci-images \
    --base $BRANCH_NAME \
    --head $GITHUB_USER:$BRANCH_NAME \
    --title "Branch: $BRANCH_NAME" \
    --body "Branch \`$BRANCH_NAME\` for Foreman $VERSION release.

  Pins Candlepin VERSION to $CANDLEPIN_VERSION and updates Makefile image tags.

  Part of the Foreman $VERSION Konflux branching process." \
    --draft
  ```

---

## Phase 4 — Wait for RPM availability

> *Or run: `uv run hack/branch-release/branch_konflux --version=3.19 --step=wait-rpms`*
> *Skip with `--skip-rpm-check` during testing.*

OCI branches (Phases 1–3) can be created before RPMs exist. The RPM gate
controls only when the tenants-config MR is merged.

- [ ] **4.1** Poll the RPM check URL until it returns HTTP 200:

  ```bash
  echo "Polling: $RPM_CHECK_URL"

  while true; do
    STATUS=$(curl -o /dev/null -s -w "%{http_code}" "$RPM_CHECK_URL")
    echo "$(date '+%H:%M:%S') — HTTP $STATUS"
    if [ "$STATUS" = "200" ]; then
      echo "RPMs are available."
      break
    elif [ "$STATUS" = "404" ]; then
      echo "ERROR: Got 404 — check that RPM_CHECK_URL is correct for this version."
      break
    fi
    sleep 60
  done
  ```

  **Expected output when ready:** `RPMs are available.`

---

## Phase 5 — Generate tenants-config overlays

> *Or run: `uv run hack/branch-release/branch_konflux --version=3.19 --step=branch-tenants`*

This phase registers the versioned Konflux `Application`, `Component`, and
`ReleasePlan` resources by opening a MR against
[tenants-config](https://gitlab.com/fedora/infrastructure/konflux/tenants-config).

**Important:** each versioned release needs its own Konflux Application (e.g.
`pulp-3-19`) to prevent snapshot contamination with the develop components.
Without this, a build of `pulp-3-19` creates a snapshot that also includes
`pulp-develop`, causing both ReleasePlans to fire.

**Wait until OCI PRs are merged before merging this MR.**

### 5.1 Clone tenants-config

- [ ] Clone with both remotes:

  ```bash
  cd $WORKTREE_DIR/konflux-branch-$VERSION
  git clone git@gitlab.com:fedora/infrastructure/konflux/tenants-config.git --origin upstream
  cd tenants-config
  git remote add origin git@gitlab.com:$GITLAB_USER/tenants-config.git
  ```

- [ ] Create the MR branch:

  ```bash
  git checkout -b branch-$BRANCH_NAME upstream/main
  ```

### 5.2 Generate overlays for each project

The tenant path for the Foreman project is:
`clusters/kflux-fedora-01/tenants/theforeman-org-tenant`

```bash
TENANT=clusters/kflux-fedora-01/tenants/theforeman-org-tenant
```

Repeat the following pattern for each project (`foreman`, `pulp`, `candlepin`).
The examples below use the `foreman` project; substitute accordingly.

**Note on Kubernetes names:** Kubernetes resource names must not contain dots.
Use `$VERSION_K8S` (e.g. `3-19`) for all `name:`, `componentName:`, and
`suffix:` fields. The directory path `$VERSION` (e.g. `3.19`) can keep dots.

#### foreman project

- [ ] Create overlay directories:

  ```bash
  mkdir -p $TENANT/foreman/components/$VERSION
  mkdir -p $TENANT/foreman/releaseplans/$VERSION
  ```

- [ ] Write the Application CRD (gives versioned components their own scope):

  ```bash
  cat > $TENANT/foreman/components/$VERSION/application.yaml << EOF
  ---
  apiVersion: appstudio.redhat.com/v1alpha1
  kind: Application
  metadata:
    name: foreman-${VERSION_K8S}
    namespace: theforeman-org-tenant
  spec:
    displayName: Foreman ${VERSION}
  EOF
  ```

- [ ] Write `kustomization.yaml` (includes both Application and Component):

  ```bash
  cat > $TENANT/foreman/components/$VERSION/kustomization.yaml << 'EOF'
  ---
  apiVersion: kustomize.config.k8s.io/v1beta1
  kind: Kustomization
  resources:
    - application.yaml
    - components.yaml
  EOF
  ```

- [ ] Write `components.yaml` (use `$VERSION_K8S` for all K8s names, versioned Application):

  ```bash
  cat > $TENANT/foreman/components/$VERSION/components.yaml << EOF
  ---
  apiVersion: appstudio.redhat.com/v1alpha1
  kind: Component
  metadata:
    annotations:
      build.appstudio.openshift.io/pipeline: '{"name":"docker-build-oci-ta","bundle":"latest"}'
      git-provider: github
      git-provider-url: https://github.com
    name: foreman-${VERSION_K8S}
    namespace: theforeman-org-tenant
  spec:
    application: foreman-${VERSION_K8S}
    componentName: foreman-${VERSION_K8S}
    containerImage: quay.io/foreman/foreman-stage
    source:
      git:
        context: images/foreman
        dockerfileUrl: Containerfile
        revision: ${BRANCH_NAME}
        url: https://github.com/theforeman/foreman-oci-images.git
  ---
  apiVersion: appstudio.redhat.com/v1alpha1
  kind: Component
  metadata:
    annotations:
      build.appstudio.openshift.io/pipeline: '{"name":"docker-build-oci-ta","bundle":"latest"}'
      git-provider: github
      git-provider-url: https://github.com
    name: foreman-proxy-${VERSION_K8S}
    namespace: theforeman-org-tenant
  spec:
    application: foreman-${VERSION_K8S}
    componentName: foreman-proxy-${VERSION_K8S}
    containerImage: quay.io/foreman/foreman-proxy-stage
    source:
      git:
        context: images/foreman-proxy
        dockerfileUrl: Containerfile
        revision: ${BRANCH_NAME}
        url: https://github.com/theforeman/foreman-oci-images.git
  EOF
  ```

- [ ] Write the ReleasePlan overlay. Foreman uses `RELEASE_TAGS` for image tags.
  Override `spec.application` to the versioned app:

  ```bash
  FOREMAN_TAGS_YAML=$(for t in $RELEASE_TAGS; do printf '              - "%s"\n' "$t"; done)

  cat > $TENANT/foreman/releaseplans/$VERSION/kustomization.yaml << EOF
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
      suffix: "-${VERSION_K8S}"
      fieldSpecs:
      - kind: ReleasePlan
        path: metadata/name
  patches:
    - target:
        kind: ReleasePlan
      patch: |-
        - op: replace
          path: /spec/application
          value: foreman-${VERSION_K8S}
        - op: replace
          path: /spec/data/mapping/components
          value:
            - name: foreman-${VERSION_K8S}
              repository: quay.io/foreman/foreman
              tags:
  ${FOREMAN_TAGS_YAML}
            - name: foreman-proxy-${VERSION_K8S}
              repository: quay.io/foreman/foreman-proxy
              tags:
  ${FOREMAN_TAGS_YAML}
  EOF
  ```

- [ ] Add `$VERSION/` to the parent kustomization files:

  ```bash
  yq -i '.resources += ["'$VERSION'/"]' $TENANT/foreman/components/kustomization.yaml
  yq -i '.resources += ["'$VERSION'/"]' $TENANT/foreman/releaseplans/kustomization.yaml
  ```

#### pulp project

- [ ] Create overlay directories:

  ```bash
  mkdir -p $TENANT/pulp/components/$VERSION
  mkdir -p $TENANT/pulp/releaseplans/$VERSION
  ```

- [ ] Write Application CRD, kustomization.yaml, and components.yaml:

  ```bash
  cat > $TENANT/pulp/components/$VERSION/application.yaml << EOF
  ---
  apiVersion: appstudio.redhat.com/v1alpha1
  kind: Application
  metadata:
    name: pulp-${VERSION_K8S}
    namespace: theforeman-org-tenant
  spec:
    displayName: Pulp ${VERSION}
  EOF

  cat > $TENANT/pulp/components/$VERSION/kustomization.yaml << 'EOF'
  ---
  apiVersion: kustomize.config.k8s.io/v1beta1
  kind: Kustomization
  resources:
    - application.yaml
    - components.yaml
  EOF

  cat > $TENANT/pulp/components/$VERSION/components.yaml << EOF
  ---
  apiVersion: appstudio.redhat.com/v1alpha1
  kind: Component
  metadata:
    annotations:
      build.appstudio.openshift.io/pipeline: '{"name":"docker-build-oci-ta","bundle":"latest"}'
      git-provider: github
      git-provider-url: https://github.com
    name: pulp-${VERSION_K8S}
    namespace: theforeman-org-tenant
  spec:
    application: pulp-${VERSION_K8S}
    componentName: pulp-${VERSION_K8S}
    containerImage: quay.io/foreman/pulp-stage
    source:
      git:
        context: images/pulp
        dockerfileUrl: images/pulp/Containerfile
        revision: ${BRANCH_NAME}
        url: https://github.com/theforeman/pulp-oci-images.git
  EOF
  ```

- [ ] Write the ReleasePlan overlay. Pulp uses project version + foreman-context tag.
  `singleComponentMode: true` is required for single-component projects:

  ```bash
  cat > $TENANT/pulp/releaseplans/$VERSION/kustomization.yaml << EOF
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
      suffix: "-${VERSION_K8S}"
      fieldSpecs:
      - kind: ReleasePlan
        path: metadata/name
  patches:
    - target:
        kind: ReleasePlan
      patch: |-
        - op: add
          path: /spec/data/mapping/defaultPushOptions
          value:
            singleComponentMode: true
        - op: replace
          path: /spec/application
          value: pulp-${VERSION_K8S}
        - op: replace
          path: /spec/data/mapping/components
          value:
            - name: pulp-${VERSION_K8S}
              repository: quay.io/foreman/pulp
              tags:
                - "${PULP_VERSION}"
                - "${FOREMAN_TAG}"
  EOF
  ```

- [ ] Add `$VERSION/` to parent kustomization files:

  ```bash
  yq -i '.resources += ["'$VERSION'/"]' $TENANT/pulp/components/kustomization.yaml
  yq -i '.resources += ["'$VERSION'/"]' $TENANT/pulp/releaseplans/kustomization.yaml
  ```

#### candlepin project

- [ ] Create overlay directories:

  ```bash
  mkdir -p $TENANT/candlepin/components/$VERSION
  mkdir -p $TENANT/candlepin/releaseplans/$VERSION
  ```

- [ ] Write Application CRD, kustomization.yaml, and components.yaml:

  ```bash
  cat > $TENANT/candlepin/components/$VERSION/application.yaml << EOF
  ---
  apiVersion: appstudio.redhat.com/v1alpha1
  kind: Application
  metadata:
    name: candlepin-${VERSION_K8S}
    namespace: theforeman-org-tenant
  spec:
    displayName: Candlepin ${VERSION}
  EOF

  cat > $TENANT/candlepin/components/$VERSION/kustomization.yaml << 'EOF'
  ---
  apiVersion: kustomize.config.k8s.io/v1beta1
  kind: Kustomization
  resources:
    - application.yaml
    - components.yaml
  EOF

  cat > $TENANT/candlepin/components/$VERSION/components.yaml << EOF
  ---
  apiVersion: appstudio.redhat.com/v1alpha1
  kind: Component
  metadata:
    annotations:
      build.appstudio.openshift.io/pipeline: '{"name":"docker-build-oci-ta","bundle":"latest"}'
      git-provider: github
      git-provider-url: https://github.com
    name: candlepin-${VERSION_K8S}
    namespace: theforeman-org-tenant
  spec:
    application: candlepin-${VERSION_K8S}
    componentName: candlepin-${VERSION_K8S}
    containerImage: quay.io/foreman/candlepin-stage
    source:
      git:
        context: images/candlepin
        dockerfileUrl: Containerfile
        revision: ${BRANCH_NAME}
        url: https://github.com/theforeman/candlepin-oci-images.git
  EOF
  ```

- [ ] Write the ReleasePlan overlay. Candlepin uses project version tags + foreman-context tag:

  ```bash
  cat > $TENANT/candlepin/releaseplans/$VERSION/kustomization.yaml << EOF
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
      suffix: "-${VERSION_K8S}"
      fieldSpecs:
      - kind: ReleasePlan
        path: metadata/name
  patches:
    - target:
        kind: ReleasePlan
      patch: |-
        - op: add
          path: /spec/data/mapping/defaultPushOptions
          value:
            singleComponentMode: true
        - op: replace
          path: /spec/application
          value: candlepin-${VERSION_K8S}
        - op: replace
          path: /spec/data/mapping/components
          value:
            - name: candlepin-${VERSION_K8S}
              repository: quay.io/foreman/candlepin
              tags:
                - "${CANDLEPIN_VERSION}"
                - "${CANDLEPIN_VERSION_XYZ}"
                - "${FOREMAN_TAG}"
  EOF
  ```

- [ ] Add `$VERSION/` to parent kustomization files:

  ```bash
  yq -i '.resources += ["'$VERSION'/"]' $TENANT/candlepin/components/kustomization.yaml
  yq -i '.resources += ["'$VERSION'/"]' $TENANT/candlepin/releaseplans/kustomization.yaml
  ```

### 5.3 Validate the kustomize build

- [ ] Run kustomize build for each project to confirm the generated YAML is valid:

  ```bash
  cd $WORKTREE_DIR/konflux-branch-$VERSION/tenants-config
  for project in foreman pulp candlepin; do
    echo "=== $project components ===" && kustomize build $TENANT/$project/components/$VERSION
    echo "=== $project releaseplans ===" && kustomize build $TENANT/$project/releaseplans/$VERSION
  done
  ```

  **Expected output:** valid Kubernetes YAML for each project. Zero errors.
  Confirm that:
  - Component `name:` fields use hyphens not dots (e.g. `foreman-3-19`)
  - Component `spec.application` matches the Application CRD name (e.g. `foreman-3-19`)
  - ReleasePlan patch sets `spec.application` to the versioned name

### 5.4 Commit and push

- [ ] Commit all changes:

  ```bash
  cd $WORKTREE_DIR/konflux-branch-$VERSION/tenants-config
  git add $TENANT
  git commit -m "Add $BRANCH_NAME Components, Applications, and ReleasePlans"
  ```

- [ ] Push to your fork:

  ```bash
  git push origin branch-$BRANCH_NAME
  ```

### 5.5 Open the MR

- [ ] Open an MR against tenants-config `main` (use env vars, not `--hostname`):

  ```bash
  GLAB_HOST=gitlab.com GITLAB_HOST=gitlab.com glab mr create \
    --source-branch branch-$BRANCH_NAME \
    --target-branch main \
    --title "Branch $BRANCH_NAME: register Konflux components" \
    --description "Register Konflux Application, Component, and ReleasePlan resources
  for Foreman $VERSION (\`$BRANCH_NAME\`).

  **Merge after:**
  - OCI repo PRs for \`$BRANCH_NAME\` have been merged
  - RPMs are available at $RPM_CHECK_URL"
  ```

  **Expected output:** a GitLab MR URL. **Do not merge this MR yet** — see
  [Phase 7](#phase-7--merge-sequence).

---

## Phase 6 — Fix Konflux-generated .tekton files

After the tenants-config MR is merged, Konflux opens PRs in each OCI repo
with generated `.tekton` pipeline files. These files require manual fixes
**before merging**. See [issue #47](https://github.com/theforeman/theforeman-rel-eng-konflux/issues/47)
for the long-term plan to automate this.

For each Konflux-generated `.tekton` PR, apply the following fixes.

### 6.1 Replace the upstream buildah-oci-ta bundle

The generated files reference the upstream bundle which uses default memory/CPU
limits that cause OOM failures on large Foreman images.

Get the current digest of our custom bundle:

```bash
CUSTOM_BUNDLE_DIGEST=$(skopeo inspect docker://quay.io/foreman/tekton-catalog/task-buildah-oci-ta:0.9 | jq -r .Digest)
echo "Custom bundle digest: $CUSTOM_BUNDLE_DIGEST"
```

Apply the substitution to all `.tekton` files in the PR's branch:

```bash
# Run from the repo root after checking out the Konflux PR branch
OLD_BUNDLE="quay.io/konflux-ci/tekton-catalog/task-buildah-oci-ta:0.9@sha256:.*"
NEW_BUNDLE="quay.io/foreman/tekton-catalog/task-buildah-oci-ta@${CUSTOM_BUNDLE_DIGEST}"

for f in .tekton/*-pull-request.yaml .tekton/*-push.yaml; do
  sed -i "s|quay.io/konflux-ci/tekton-catalog/task-buildah-oci-ta:0\.9@sha256:[a-f0-9]*|${NEW_BUNDLE}|g" "$f"
done
```

### 6.2 Enable source image builds

The generated files default `build-source-image` to `"false"`. Source images
are required for production Quay pushes. Fix in every `.tekton` file:

```bash
for f in .tekton/*.yaml; do
  sed -i 's/- default: "false"\n      description: Build a source image\./- default: "true"\n      description: Build a source image./' "$f" || \
  python3 -c "
import pathlib, sys
p = pathlib.Path('$f')
c = p.read_text()
c = c.replace(
    '    - default: \"false\"\n      description: Build a source image.',
    '    - default: \"true\"\n      description: Build a source image.'
)
p.write_text(c)
print('patched:', '$f')
"
done
```

### 6.3 Add ADDITIONAL_TAGS to pull-request pipelines

PR pipeline builds should be tagged with the PR number for traceability.
Insert after the `IMAGE_DIGEST` parameter, before `runAfter: [build-image-index]`:

```bash
ANCHOR='        value: $(tasks.build-image-index.results.IMAGE_DIGEST)
      runAfter:
      - build-image-index'
REPLACEMENT='        value: $(tasks.build-image-index.results.IMAGE_DIGEST)
      - name: ADDITIONAL_TAGS
        value: 
         - "pull-request-{{pull_request_number}}"
      runAfter:
      - build-image-index'

for f in .tekton/*-pull-request.yaml; do
  python3 -c "
import pathlib
p = pathlib.Path('$f')
c = p.read_text()
if 'ADDITIONAL_TAGS' not in c:
    c = c.replace('''$ANCHOR''', '''$REPLACEMENT''', 1)
    p.write_text(c)
    print('patched:', '$f')
"
done
```

### 6.4 Fix the application annotation

The generated files set `appstudio.openshift.io/application` to the develop
application name (e.g. `foreman`). It must point to the versioned application:

```bash
# Adjust the sed pattern for each repo:
# foreman-oci-images:
sed -i "s/appstudio.openshift.io\/application: foreman$/appstudio.openshift.io\/application: foreman-${VERSION_K8S}/g" .tekton/*.yaml

# pulp-oci-images:
sed -i "s/appstudio.openshift.io\/application: pulp$/appstudio.openshift.io\/application: pulp-${VERSION_K8S}/g" .tekton/*.yaml

# candlepin-oci-images:
sed -i "s/appstudio.openshift.io\/application: candlepin$/appstudio.openshift.io\/application: candlepin-${VERSION_K8S}/g" .tekton/*.yaml
```

### 6.5 Commit and push the fixes

```bash
git add .tekton/
git commit -m ".tekton: custom buildah bundle, enable source image, add PR tag, fix application"
git push
```

---

## Phase 7 — Merge sequence

> The three OCI repo PRs and the tenants-config MR must be merged in this order.

- [ ] **7.1** Get reviews and approvals for all three OCI repo branching PRs.

- [ ] **7.2** Merge the `foreman-oci-images` branching PR:

  ```bash
  FOREMAN_PR=$(gh pr list --repo theforeman/foreman-oci-images \
    --head $GITHUB_USER:$BRANCH_NAME --json number -q '.[0].number')
  gh pr merge "$FOREMAN_PR" --repo theforeman/foreman-oci-images --merge
  ```

- [ ] **7.3** Merge the `pulp-oci-images` branching PR:

  ```bash
  PULP_PR=$(gh pr list --repo theforeman/pulp-oci-images \
    --head $GITHUB_USER:$BRANCH_NAME --json number -q '.[0].number')
  gh pr merge "$PULP_PR" --repo theforeman/pulp-oci-images --merge
  ```

- [ ] **7.4** Merge the `candlepin-oci-images` branching PR:

  ```bash
  CP_PR=$(gh pr list --repo theforeman/candlepin-oci-images \
    --head $GITHUB_USER:$BRANCH_NAME --json number -q '.[0].number')
  gh pr merge "$CP_PR" --repo theforeman/candlepin-oci-images --merge
  ```

- [ ] **7.5** Merge the Konflux-generated `.tekton` PRs (after applying the fixes from
  [Phase 6](#phase-6--fix-konflux-generated-tekton-files)):

  ```bash
  # Find and merge each .tekton PR
  for repo in foreman-oci-images pulp-oci-images candlepin-oci-images; do
    gh pr list --repo theforeman/$repo --json number,headRefName \
      --jq '.[] | select(.headRefName | startswith("konflux-")) | .number' \
    | xargs -I{} gh pr merge {} --repo theforeman/$repo --merge
  done
  ```

- [ ] **7.6** Confirm RPMs are available (HTTP 200):

  ```bash
  curl -o /dev/null -s -w "%{http_code}" "$RPM_CHECK_URL"
  ```

  **Expected output:** `200`

- [ ] **7.7** Merge the tenants-config MR:

  ```bash
  GLAB_HOST=gitlab.com GITLAB_HOST=gitlab.com \
    glab mr merge branch-$BRANCH_NAME \
    --source-branch branch-$BRANCH_NAME
  ```

  ArgoCD reconciles the new resources automatically after the MR is merged
  (allow a few minutes).

---

## Phase 8 — Verify in Konflux UI

- [ ] **8.1** Navigate to the Konflux console:
  https://konflux.fedoraproject.org

- [ ] **8.2** Confirm the following versioned Applications and Components appear:
  - Application `foreman-3-19` → components `foreman-3-19`, `foreman-proxy-3-19`
  - Application `pulp-3-19` → component `pulp-3-19`
  - Application `candlepin-3-19` → component `candlepin-3-19`

- [ ] **8.3** Verify images are published on Quay after the first successful build:

  ```bash
  # Foreman
  skopeo inspect docker://quay.io/foreman/foreman:$VERSION | jq -r .Digest

  # Foreman proxy
  skopeo inspect docker://quay.io/foreman/foreman-proxy:$VERSION | jq -r .Digest

  # Pulp (foremanctl pulls via foreman-prefixed tag)
  skopeo inspect docker://quay.io/foreman/pulp:$FOREMAN_TAG | jq -r .Digest

  # Candlepin (foremanctl pulls via foreman-prefixed tag)
  skopeo inspect docker://quay.io/foreman/candlepin:$FOREMAN_TAG | jq -r .Digest
  ```

- [ ] **8.4** Clean up temporary worktrees:

  ```bash
  rm -rf $WORKTREE_DIR/konflux-branch-$VERSION
  ```

---

## Troubleshooting

### 1. glab authentication or host errors

**Symptom:** `401 Unauthorized`, `404 Not Found` on glab commands, or
`None of the git remotes... correspond to the GITLAB_HOST environment variable`.

**Diagnosis:**

```bash
# Check which host glab is targeting
env | grep -i gitlab
env | grep -i glab
```

Common causes:
- `GITLAB_HOST` set to a non-public GitLab instance (e.g. `gitlab.cee.redhat.com`)
- `GITLAB_TOKEN` set to a stale/wrong token that overrides stored credentials
- Using `--hostname` flag which is not supported on all glab subcommands

**Fix:**

```bash
# Always set both host variables and unset stale token before using glab:
export GLAB_HOST=gitlab.com
export GITLAB_HOST=gitlab.com
unset GITLAB_TOKEN

# Use full URL for repo view (short namespace/repo form returns 404):
GLAB_HOST=gitlab.com GITLAB_HOST=gitlab.com \
  glab repo view https://gitlab.com/$GITLAB_USER/tenants-config
```

### 2. Kubernetes name validation failure

**Symptom:** Component or Application rejected with:
> `spec.componentName: Invalid value: "pulp-3.19": should match '^[a-z0-9]([-a-z0-9]*[a-z0-9])?$'`

**Cause:** Kubernetes resource names must not contain dots. Version `3.19`
must become `3-19` in all resource `name:`, `componentName:`, `suffix:`,
and annotation values.

**Fix:** Ensure `VERSION_K8S=${VERSION//./-}` is set and used for all
Kubernetes resource name fields. Directory paths (`3.19/`) can keep dots.

### 3. Two releases fired for one build

**Symptom:** A build of `pulp-3-19` triggers two Release objects — one for
the versioned ReleasePlan and one for the develop ReleasePlan.

**Cause:** The versioned component is in the same Konflux Application as
`pulp-develop`. Konflux snapshots are Application-scoped, so a build of
`pulp-3-19` creates a snapshot that includes `pulp-develop`, and both
ReleasePlans fire.

**Fix:** Each versioned release must have its own Application CRD
(e.g. `pulp-3-19`) with `spec.application: pulp-3-19` in the Component
and ReleasePlan. See [Phase 5.2](#52-generate-overlays-for-each-project).

### 4. foremanctl cannot pull pulp/candlepin images

**Symptom:** Integration test fails with:
> `Failed to pull image quay.io/foreman/candlepin:foreman-3.19`

**Cause:** foremanctl (`src/vars/images.yml`) constructs pulp/candlepin
image tags as `foreman-{{ container_tag_stream }}`, not `{{ container_tag_stream }}`.
The ReleasePlan must include `foreman-3.19` in the tags for these images.

**Fix:** Ensure ReleasePlan tags for pulp and candlepin include `$FOREMAN_TAG`:
- `pulp`: `["3.105", "foreman-3.19"]`
- `candlepin`: `["4.7", "4.7.4", "foreman-3.19"]`

See [Phase 5.2](#52-generate-overlays-for-each-project).

### 5. Missing fork or wrong remote config

**Symptom:** `validate_fork` fails, `gh pr create` errors with `not found`, or
`git push origin` is rejected with permission denied.

**Diagnosis:**

```bash
gh repo view $GITHUB_USER/foreman-oci-images 2>&1
git remote -v
```

**Fix:**

- If a fork is missing, create it from the GitHub/GitLab UI.
- If a remote name is wrong, rename it:

  ```bash
  git remote rename <wrong-name> upstream   # or: origin
  ```

### 6. RPM repo not yet available

**Symptom:** polling loop returns HTTP 404 consistently.

**Fix:** verify `RPM_CHECK_URL` in the settings file (check el version, arch,
version number). To skip the gate during testing:

```bash
uv run hack/branch-release/branch_konflux --version=$VERSION \
  --step=branch-tenants --skip-rpm-check
```

Do not merge the tenants-config MR until RPMs are genuinely available.

### 7. kustomize validation failure

**Symptom:** `kustomize build` exits non-zero.

**Fix:**

```bash
kustomize build $TENANT/foreman/components/$VERSION 2>&1
```

Common causes: YAML indentation error, missing `resources:` entry, reference
to `../base` that doesn't exist. Correct the YAML, commit, push — the MR
updates automatically.
