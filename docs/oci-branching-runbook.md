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
- [Phase 6 — Merge sequence](#phase-6--merge-sequence)
- [Phase 7 — Verify in Konflux UI](#phase-7--verify-in-konflux-ui)
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
glab auth status
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

Verify the GitLab fork:

```bash
glab repo view $GITLAB_USER/tenants-config --hostname gitlab.com
```

### Remote naming convention

All scripts enforce the following remote naming. Verify your local remotes match
before starting.

| Remote | Points to |
|--------|-----------|
| `upstream` | The `theforeman/` (or `fedora/`) org repository |
| `origin` | Your personal fork |

If you prefer SSH for pushing, substitute SSH remote URLs when adding the `origin`
remote (e.g., `git remote add origin git@github.com:$GITHUB_USER/foreman-oci-images.git`).
The HTTPS URLs shown throughout this runbook work with HTTPS token authentication.

### Settings file

Create the release settings file at `releases/foreman/3.19/settings` (adjust
path for your version):

```bash
mkdir -p releases/foreman/3.19
```

Populate it with the following key=value pairs. This file is distinct from
`hack/branch-release/settings.example`, which holds your personal GitHub/GitLab
identity settings — create that separately if you haven't already (see the
comments inside `settings.example`):

```bash
# releases/foreman/3.19/settings
VERSION=3.19
BRANCH_NAME=foreman-3.19
OCI_REPOS="theforeman/foreman-oci-images theforeman/pulp-oci-images theforeman/candlepin-oci-images"
RELEASE_TAGS="3.19 3.19.0"
RPM_CHECK_URL=https://yum.theforeman.org/releases/3.19/el9/x86_64/repodata/repomd.xml
RPM_CHECK_TIMEOUT=14400
KATELLO_VERSION=<katello-version>
CANDLEPIN_VERSION=<candlepin-version>
CANDLEPIN_VERSION_XYZ=<candlepin-version-xyz>
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
export VERSION=3.19
export BRANCH_NAME=foreman-3.19
export WORKTREE_DIR=/tmp   # optional — override if /tmp is too small or restricted

# Source the release settings file — sets KATELLO_VERSION, CANDLEPIN_VERSION,
# CANDLEPIN_VERSION_XYZ, RELEASE_TAGS, RPM_CHECK_URL, RPM_CHECK_TIMEOUT, etc.
source releases/foreman/$VERSION/settings

# Pre-compute TAGS_YAML for use in tenants-config heredocs (Phase 5)
export TAGS_YAML=$(for t in $RELEASE_TAGS; do printf '              - "%s"\n' "$t"; done)
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

- [ ] **0.3** Confirm GitLab CLI is authenticated:

  ```bash
  glab auth status
  ```

  **Expected output:** `You are logged in to gitlab.com as <username>`.

- [ ] **0.4** Verify GitHub forks exist:

  ```bash
  gh repo view $GITHUB_USER/foreman-oci-images --json name -q .name
  gh repo view $GITHUB_USER/pulp-oci-images --json name -q .name
  gh repo view $GITHUB_USER/candlepin-oci-images --json name -q .name
  ```

  **Expected output:** repository names (`foreman-oci-images`, etc.). A 404 means the fork is missing — create it from the GitHub UI before continuing.

- [ ] **0.5** Verify GitLab fork exists:

  ```bash
  glab repo view $GITLAB_USER/tenants-config --hostname gitlab.com
  ```

  **Expected output:** repository details. If it fails, create the fork at
  https://gitlab.com/fedora/infrastructure/konflux/tenants-config.

- [ ] **0.6** Check for an existing versioned Konflux component (warn only):

  ```bash
  oc get component foreman-$VERSION -n theforeman-org-tenant 2>/dev/null \
    && echo "WARNING: component already exists — proceed with caution" \
    || echo "ok — component does not exist"
  ```

  **Expected output for a fresh branch:** `ok — component does not exist`.
  If the component already exists, the `branch-tenants` phase may produce
  duplicate resources; review carefully before proceeding.

  **Note:** this checks only the `foreman-$VERSION` component. If a prior
  partial run exists, `foreman-proxy-$VERSION`, `pulp-$VERSION`, or
  `candlepin-$VERSION` may also already exist. Check all four if you suspect
  a prior partial run:

  ```bash
  for c in foreman foreman-proxy pulp candlepin; do
    oc get component ${c}-$VERSION -n theforeman-org-tenant 2>/dev/null \
      && echo "EXISTS: ${c}-$VERSION" || true
  done
  ```

- [ ] **0.7** Confirm the settings file exists and is parseable:

  ```bash
  cat releases/foreman/$VERSION/settings
  ```

  **Expected output:** the key=value pairs you created in [Prerequisites](#prerequisites).

---

## Phase 1 — Branch foreman-oci-images

> *Or run: `uv run hack/branch-release/branch_konflux --version=3.19 --step=branch-oci-foreman-oci-images`*

**Precondition:** nightly CI on `master` must be passing before cutting the
release branch. Confirm at the [Konflux console](https://console.redhat.com/application-pipeline/workspaces/theforeman-org/applications) or in the GitHub status checks on `master`. Do not proceed with a broken nightly.

- [ ] **1.1** Detect the default branch:

  ```bash
  DEFAULT_BRANCH=$(gh repo view theforeman/foreman-oci-images --json defaultBranchRef -q .defaultBranchRef.name)
  echo "Default branch: $DEFAULT_BRANCH"
  ```

  **Expected output:** `Default branch: master`

- [ ] **1.2** Clone into a temporary worktree with both remotes:

  ```bash
  mkdir -p /tmp/konflux-branch-$VERSION
  cd /tmp/konflux-branch-$VERSION
  git clone https://github.com/theforeman/foreman-oci-images.git
  cd foreman-oci-images
  git remote rename origin upstream
  git remote add origin https://github.com/$GITHUB_USER/foreman-oci-images.git
  ```

  **Expected output:** normal git clone output. Verify remotes:

  ```bash
  git remote -v
  ```

  You should see `upstream` pointing to `theforeman/` and `origin` pointing to
  your fork.

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

- [ ] **1.5** Patch Containerfile ARG values to pin release versions
  (`KATELLO_VERSION` was loaded by `source releases/foreman/$VERSION/settings`
  in the Environment Variables setup).

  Patch `images/foreman/Containerfile`:

  ```bash
  sed -i "s|^ARG FOREMAN_VERSION=.*|ARG FOREMAN_VERSION=$VERSION|" images/foreman/Containerfile
  sed -i "s|^ARG KATELLO_VERSION=.*|ARG KATELLO_VERSION=$KATELLO_VERSION|" images/foreman/Containerfile
  ```

  Patch `images/foreman-proxy/Containerfile`:

  ```bash
  sed -i "s|^ARG FOREMAN_VERSION=.*|ARG FOREMAN_VERSION=$VERSION|" images/foreman-proxy/Containerfile
  ```

  **Verify the patches:**

  ```bash
  grep "^ARG FOREMAN_VERSION\|^ARG KATELLO_VERSION" images/foreman/Containerfile
  grep "^ARG FOREMAN_VERSION" images/foreman-proxy/Containerfile
  ```

  **Expected output:**

  ```
  ARG FOREMAN_VERSION=3.19
  ARG KATELLO_VERSION=<katello-version>
  ARG FOREMAN_VERSION=3.19
  ```

  **Note:** `KATELLO_VERSION` is intentionally not patched in
  `images/foreman-proxy/Containerfile`. The proxy image does not use
  `KATELLO_VERSION` at build time; only `FOREMAN_VERSION` is set there.

- [ ] **1.6** Commit the Containerfile patches:

  ```bash
  git add images/foreman/Containerfile images/foreman-proxy/Containerfile
  git commit -m "Branch $BRANCH_NAME: patch Containerfile versions"
  ```

  **Expected output:** commit created with the message above.

- [ ] **1.7** Push the branch to your fork:

  ```bash
  git push -u origin $BRANCH_NAME
  ```

  **Expected output:** `Branch 'foreman-3.19' set up to track remote branch 'foreman-3.19' from 'origin'.`

- [ ] **1.8** Open a draft PR against the upstream default branch. Save the PR
  number from the output — you will use it in [Phase 6](#phase-6--merge-sequence):

  ```bash
  gh pr create \
    --repo theforeman/foreman-oci-images \
    --base $DEFAULT_BRANCH \
    --head $GITHUB_USER:$BRANCH_NAME \
    --title "Branch: $BRANCH_NAME" \
    --body "Branch \`$BRANCH_NAME\` for Foreman $VERSION release.

  This PR patches Containerfile ARG values to pin the release version.

  Part of the Foreman $VERSION Konflux branching process." \
    --draft
  ```

  **Expected output:** a GitHub PR URL. Save it — you will need it in [Phase 6](#phase-6--merge-sequence).

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
  cd /tmp/konflux-branch-$VERSION
  git clone https://github.com/theforeman/pulp-oci-images.git
  cd pulp-oci-images
  git remote rename origin upstream
  git remote add origin https://github.com/$GITHUB_USER/pulp-oci-images.git
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

- [ ] **2.5** `pulp-oci-images` has `ARG VERSION=nightly` in its Containerfile,
  but this value is intentionally left unpinned. The Pulp version is independent
  of the Foreman release version and is not patched during branching. No
  Containerfile changes are needed.

- [ ] **2.6** Push the branch to your fork:

  ```bash
  git push -u origin $BRANCH_NAME
  ```

  **Expected output:** `Branch 'foreman-3.19' set up to track remote branch 'foreman-3.19' from 'origin'.`

- [ ] **2.7** Open a draft PR. Save the PR number:

  ```bash
  gh pr create \
    --repo theforeman/pulp-oci-images \
    --base $DEFAULT_BRANCH_PULP \
    --head $GITHUB_USER:$BRANCH_NAME \
    --title "Branch: $BRANCH_NAME" \
    --body "Branch \`$BRANCH_NAME\` for Foreman $VERSION release.

  Part of the Foreman $VERSION Konflux branching process." \
    --draft
  ```

  **Expected output:** a GitHub PR URL.

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
  cd /tmp/konflux-branch-$VERSION
  git clone https://github.com/theforeman/candlepin-oci-images.git
  cd candlepin-oci-images
  git remote rename origin upstream
  git remote add origin https://github.com/$GITHUB_USER/candlepin-oci-images.git
  ```

- [ ] **3.3** Check for existing branch:

  ```bash
  git ls-remote upstream refs/heads/$BRANCH_NAME
  ```

  **Expected output for a fresh branch:** empty.

- [ ] **3.4** Create the release branch:

  ```bash
  git checkout -b $BRANCH_NAME upstream/$DEFAULT_BRANCH_CP
  ```

- [ ] **3.5** Patch `images/candlepin/Containerfile` (`CANDLEPIN_VERSION` and
  `CANDLEPIN_VERSION_XYZ` were loaded by `source releases/foreman/$VERSION/settings`
  in the Environment Variables setup):

  ```bash
  sed -i "s|^ARG CANDLEPIN_VERSION=.*|ARG CANDLEPIN_VERSION=$CANDLEPIN_VERSION|" images/candlepin/Containerfile
  sed -i "s|^ARG CANDLEPIN_VERSION_XYZ=.*|ARG CANDLEPIN_VERSION_XYZ=$CANDLEPIN_VERSION_XYZ|" images/candlepin/Containerfile
  ```

  **Verify the patches:**

  ```bash
  grep "^ARG CANDLEPIN_VERSION" images/candlepin/Containerfile
  ```

  **Expected output:**

  ```
  ARG CANDLEPIN_VERSION=<candlepin-version>
  ARG CANDLEPIN_VERSION_XYZ=<candlepin-version-xyz>
  ```

- [ ] **3.6** Commit the Containerfile patch:

  ```bash
  git add images/candlepin/Containerfile
  git commit -m "Branch $BRANCH_NAME: patch Containerfile versions"
  ```

- [ ] **3.7** Push the branch to your fork:

  ```bash
  git push -u origin $BRANCH_NAME
  ```

  **Expected output:** `Branch 'foreman-3.19' set up to track remote branch 'foreman-3.19' from 'origin'.`

- [ ] **3.8** Open a draft PR. Save the PR number:

  ```bash
  gh pr create \
    --repo theforeman/candlepin-oci-images \
    --base $DEFAULT_BRANCH_CP \
    --head $GITHUB_USER:$BRANCH_NAME \
    --title "Branch: $BRANCH_NAME" \
    --body "Branch \`$BRANCH_NAME\` for Foreman $VERSION release.

  This PR patches Containerfile ARG values to pin the release version.

  Part of the Foreman $VERSION Konflux branching process." \
    --draft
  ```

  **Expected output:** a GitHub PR URL.

---

## Phase 4 — Wait for RPM availability

> *Or run: `uv run hack/branch-release/branch_konflux --version=3.19 --step=wait-rpms`*
> *Skip with `--skip-rpm-check` during testing.*

OCI branches (Phases 1–3) can be created before RPMs exist. The RPM gate
controls only when the tenants-config MR is merged.

- [ ] **4.1** Poll the RPM check URL until it returns HTTP 200 (`RPM_CHECK_URL`
  was set by `source releases/foreman/$VERSION/settings`):

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

  - HTTP 200 → proceed to Phase 5.
  - HTTP 404 → wrong URL or version; verify `RPM_CHECK_URL` in your settings file.
  - HTTP 403 → CDN transient error; continue polling.

---

## Phase 5 — Generate tenants-config overlays

> *Or run: `uv run hack/branch-release/branch_konflux --version=3.19 --step=branch-tenants`*

This phase registers the versioned Konflux `Component` and `ReleasePlan`
resources by opening a MR against
[tenants-config](https://gitlab.com/fedora/infrastructure/konflux/tenants-config).

**Wait until OCI PRs are merged before merging this MR** (though you can open
the MR now). See [Phase 6](#phase-6--merge-sequence) for the correct merge order.

### 5.1 Clone tenants-config

- [ ] Clone with both remotes:

  ```bash
  cd /tmp/konflux-branch-$VERSION
  git clone https://gitlab.com/fedora/infrastructure/konflux/tenants-config.git
  cd tenants-config
  git remote rename origin upstream
  git remote add origin https://gitlab.com/$GITLAB_USER/tenants-config.git
  ```

- [ ] Create the MR branch:

  ```bash
  git checkout -b branch-$BRANCH_NAME upstream/main
  ```

### 5.2 Generate Component overlays

The tenant path for the Foreman project is:
`clusters/kflux-fedora-01/tenants/theforeman-org-tenant`

Repeat for each project: `foreman`, `pulp`, `candlepin`.

**foreman project:**

- [ ] Create overlay directories:

  ```bash
  TENANT=clusters/kflux-fedora-01/tenants/theforeman-org-tenant
  mkdir -p $TENANT/foreman/components/$VERSION
  mkdir -p $TENANT/foreman/releaseplans/$VERSION
  ```

- [ ] Write `$TENANT/foreman/components/$VERSION/kustomization.yaml` and
  `$TENANT/foreman/components/$VERSION/components.yaml` using the following
  commands (shell variables are expanded automatically):

  ```bash
  cat > $TENANT/foreman/components/$VERSION/kustomization.yaml << 'EOF'
  ---
  apiVersion: kustomize.config.k8s.io/v1beta1
  kind: Kustomization
  resources:
    - components.yaml
  EOF
  ```

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
    name: foreman-${VERSION}
    namespace: theforeman-org-tenant
  spec:
    application: foreman
    componentName: foreman-${VERSION}
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
    name: foreman-proxy-${VERSION}
    namespace: theforeman-org-tenant
  spec:
    application: foreman
    componentName: foreman-proxy-${VERSION}
    containerImage: quay.io/foreman/foreman-proxy-stage
    source:
      git:
        context: images/foreman-proxy
        dockerfileUrl: Containerfile
        revision: ${BRANCH_NAME}
        url: https://github.com/theforeman/foreman-oci-images.git
  EOF
  ```

  **Verify:** `cat $TENANT/foreman/components/$VERSION/components.yaml` and
  confirm `name: foreman-3.19` appears (with your actual version).

- [ ] Write `$TENANT/foreman/releaseplans/$VERSION/kustomization.yaml`
  (`TAGS_YAML` was pre-computed in the Environment Variables setup):

  ```bash
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
      suffix: "-${VERSION}"
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
            - name: foreman-${VERSION}
              repository: quay.io/foreman/foreman
              tags:
  ${TAGS_YAML}
            - name: foreman-proxy-${VERSION}
              repository: quay.io/foreman/foreman-proxy
              tags:
  ${TAGS_YAML}
  EOF
  ```

- [ ] Add `$VERSION/` to `$TENANT/foreman/components/kustomization.yaml` resources list:

  ```bash
  # Append the new overlay to the resources: block
  yq -i '.resources += ["'$VERSION'/"]' $TENANT/foreman/components/kustomization.yaml
  ```

  **Verify:**

  ```bash
  grep "$VERSION" $TENANT/foreman/components/kustomization.yaml
  ```

  **Expected output:** `  - $VERSION/`

- [ ] Add `$VERSION/` to `$TENANT/foreman/releaseplans/kustomization.yaml`:

  ```bash
  yq -i '.resources += ["'$VERSION'/"]' $TENANT/foreman/releaseplans/kustomization.yaml
  ```

**pulp project:**

- [ ] Create overlay directories:

  ```bash
  mkdir -p $TENANT/pulp/components/$VERSION
  mkdir -p $TENANT/pulp/releaseplans/$VERSION
  ```

- [ ] Write the pulp kustomization and component files:

  ```bash
  cat > $TENANT/pulp/components/$VERSION/kustomization.yaml << 'EOF'
  ---
  apiVersion: kustomize.config.k8s.io/v1beta1
  kind: Kustomization
  resources:
    - components.yaml
  EOF
  ```

  ```bash
  cat > $TENANT/pulp/components/$VERSION/components.yaml << EOF
  ---
  apiVersion: appstudio.redhat.com/v1alpha1
  kind: Component
  metadata:
    annotations:
      build.appstudio.openshift.io/pipeline: '{"name":"docker-build-oci-ta","bundle":"latest"}'
      git-provider: github
      git-provider-url: https://github.com
    name: pulp-${VERSION}
    namespace: theforeman-org-tenant
  spec:
    application: pulp
    componentName: pulp-${VERSION}
    containerImage: quay.io/foreman/pulp-stage
    source:
      git:
        context: images/pulp
        dockerfileUrl: images/pulp/Containerfile
        revision: ${BRANCH_NAME}
        url: https://github.com/theforeman/pulp-oci-images.git
  EOF
  ```

  Because pulp has a single component, include the `singleComponentMode` patch
  in the ReleasePlan overlay:

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
      suffix: "-${VERSION}"
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
          path: /spec/data/mapping/components
          value:
            - name: pulp-${VERSION}
              repository: quay.io/foreman/pulp
              tags:
  ${TAGS_YAML}
  EOF
  ```

- [ ] Add `$VERSION/` to both `pulp/components/kustomization.yaml` and `pulp/releaseplans/kustomization.yaml`:

  ```bash
  yq -i '.resources += ["'$VERSION'/"]' $TENANT/pulp/components/kustomization.yaml
  yq -i '.resources += ["'$VERSION'/"]' $TENANT/pulp/releaseplans/kustomization.yaml
  ```

**candlepin project:**

- [ ] Create overlay directories and write the candlepin files:

  ```bash
  mkdir -p $TENANT/candlepin/components/$VERSION
  mkdir -p $TENANT/candlepin/releaseplans/$VERSION
  ```

  ```bash
  cat > $TENANT/candlepin/components/$VERSION/kustomization.yaml << 'EOF'
  ---
  apiVersion: kustomize.config.k8s.io/v1beta1
  kind: Kustomization
  resources:
    - components.yaml
  EOF
  ```

  ```bash
  cat > $TENANT/candlepin/components/$VERSION/components.yaml << EOF
  ---
  apiVersion: appstudio.redhat.com/v1alpha1
  kind: Component
  metadata:
    annotations:
      build.appstudio.openshift.io/pipeline: '{"name":"docker-build-oci-ta","bundle":"latest"}'
      git-provider: github
      git-provider-url: https://github.com
    name: candlepin-${VERSION}
    namespace: theforeman-org-tenant
  spec:
    application: candlepin
    componentName: candlepin-${VERSION}
    containerImage: quay.io/foreman/candlepin-stage
    source:
      git:
        context: images/candlepin
        dockerfileUrl: Containerfile
        revision: ${BRANCH_NAME}
        url: https://github.com/theforeman/candlepin-oci-images.git
  EOF
  ```

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
      suffix: "-${VERSION}"
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
          path: /spec/data/mapping/components
          value:
            - name: candlepin-${VERSION}
              repository: quay.io/foreman/candlepin
              tags:
  ${TAGS_YAML}
  EOF
  ```

- [ ] Add `$VERSION/` to both `candlepin/components/kustomization.yaml` and
  `candlepin/releaseplans/kustomization.yaml`:

  ```bash
  yq -i '.resources += ["'$VERSION'/"]' $TENANT/candlepin/components/kustomization.yaml
  yq -i '.resources += ["'$VERSION'/"]' $TENANT/candlepin/releaseplans/kustomization.yaml
  ```

### 5.3 Validate the kustomize build

- [ ] Run kustomize build for each project to confirm the generated YAML is valid:

  ```bash
  cd /tmp/konflux-branch-$VERSION/tenants-config
  kustomize build $TENANT/foreman/components/$VERSION
  kustomize build $TENANT/foreman/releaseplans/$VERSION
  kustomize build $TENANT/pulp/components/$VERSION
  kustomize build $TENANT/pulp/releaseplans/$VERSION
  kustomize build $TENANT/candlepin/components/$VERSION
  kustomize build $TENANT/candlepin/releaseplans/$VERSION
  ```

  **Expected output:** valid Kubernetes YAML for each project. Zero errors.

### 5.4 Commit and push

- [ ] Commit all changes:

  ```bash
  cd /tmp/konflux-branch-$VERSION/tenants-config
  git add $TENANT
  git commit -m "Add $BRANCH_NAME Components and ReleasePlans"
  ```

- [ ] Push to your fork:

  ```bash
  git push origin branch-$BRANCH_NAME
  ```

### 5.5 Open the MR

- [ ] Open an MR against tenants-config `main`:

  ```bash
  glab mr create \
    --repo fedora/infrastructure/konflux/tenants-config \
    --target-branch main \
    --source-branch branch-$BRANCH_NAME \
    --title "Branch $BRANCH_NAME: register Konflux components" \
    --description "Register Konflux Component and ReleasePlan resources for Foreman $VERSION (\`$BRANCH_NAME\`).

  **Merge after:**
  - OCI repo PRs for \`$BRANCH_NAME\` have been merged
  - RPMs are available at the RPM_CHECK_URL" \
    --hostname gitlab.com
  ```

  **Expected output:** a GitLab MR URL. **Do not merge this MR yet** — see
  [Phase 6](#phase-6--merge-sequence).

---

## Phase 6 — Merge sequence

> The three OCI repo PRs and the tenants-config MR must be merged in this order.

- [ ] **6.1** Get reviews and approvals for all three OCI repo PRs
  (`foreman-oci-images`, `pulp-oci-images`, `candlepin-oci-images`). Check each
  repo's merge policy — substitute `--squash` for `--merge` below if the repo
  requires squash merges.

- [ ] **6.2** Merge the `foreman-oci-images` PR (pass the PR number saved in step 1.8,
  or let `gh` look it up by branch):

  ```bash
  FOREMAN_PR=$(gh pr list --repo theforeman/foreman-oci-images \
    --head $GITHUB_USER:$BRANCH_NAME --json number -q '.[0].number')
  gh pr merge "$FOREMAN_PR" --repo theforeman/foreman-oci-images --merge
  ```

- [ ] **6.3** Merge the `pulp-oci-images` PR:

  ```bash
  PULP_PR=$(gh pr list --repo theforeman/pulp-oci-images \
    --head $GITHUB_USER:$BRANCH_NAME --json number -q '.[0].number')
  gh pr merge "$PULP_PR" --repo theforeman/pulp-oci-images --merge
  ```

- [ ] **6.4** Merge the `candlepin-oci-images` PR:

  ```bash
  CP_PR=$(gh pr list --repo theforeman/candlepin-oci-images \
    --head $GITHUB_USER:$BRANCH_NAME --json number -q '.[0].number')
  gh pr merge "$CP_PR" --repo theforeman/candlepin-oci-images --merge
  ```

- [ ] **6.5** Confirm RPMs are available at the `RPM_CHECK_URL` (HTTP 200).
  If you skipped Phase 4, verify now:

  ```bash
  curl -o /dev/null -s -w "%{http_code}" "$RPM_CHECK_URL"
  ```

  **Expected output:** `200`

- [ ] **6.6** Merge the tenants-config MR (after OCI PRs are merged and RPMs are
  available):

  ```bash
  glab mr merge branch-$BRANCH_NAME \
    --repo fedora/infrastructure/konflux/tenants-config \
    --hostname gitlab.com
  ```

  Check the tenants-config project's merge policy before merging — use
  `--squash` if the project requires squash merges.

  ArgoCD reconciles the new Component and ReleasePlan resources automatically
  after the MR is merged (allow a few minutes).

---

## Phase 7 — Verify in Konflux UI

After the tenants-config MR is merged, verify the versioned components are
healthy in the Konflux console.

- [ ] **7.1** Navigate to the Konflux console:
  https://console.redhat.com/application-pipeline/workspaces/theforeman-org/applications

- [ ] **7.2** Open the `foreman` application and confirm the following components
  appear:
  - `foreman-$VERSION`
  - `foreman-proxy-$VERSION`

- [ ] **7.3** Open the `pulp` application and confirm `pulp-$VERSION` appears.

- [ ] **7.4** Open the `candlepin` application and confirm `candlepin-$VERSION` appears.

- [ ] **7.5** Trigger a build for each versioned component (Konflux automatically
  opens a PR on the versioned branch to update `.tekton` files once a Component is
  registered; merge that PR to trigger the first build). Confirm that builds
  complete successfully in the Konflux PipelineRun view.

- [ ] **7.6** Verify that images appear in the target Quay repositories
  (they are released with the `push-to-external-registry` ReleasePlan):
  - `quay.io/theforeman/foreman:$VERSION`
  - `quay.io/theforeman/foreman-proxy:$VERSION`
  - `quay.io/theforeman/pulp:$VERSION`
  - `quay.io/theforeman/candlepin:$VERSION`

- [ ] **7.7** Clean up temporary worktrees:

  ```bash
  rm -rf /tmp/konflux-branch-$VERSION
  ```

---

## Troubleshooting

### 1. Missing fork or wrong remote config

**Symptom:** `validate_fork` fails, `gh pr create` errors with `not found`, or
`git push origin` is rejected with permission denied.

**Diagnosis:**

```bash
# Check your GitHub forks
gh repo view $GITHUB_USER/foreman-oci-images 2>&1
gh repo view $GITHUB_USER/pulp-oci-images 2>&1
gh repo view $GITHUB_USER/candlepin-oci-images 2>&1

# Check your GitLab fork
glab repo view $GITLAB_USER/tenants-config --hostname gitlab.com 2>&1

# Check remotes in an existing worktree
git remote -v
```

**Fix:**

- If a fork is missing, create it from the upstream GitHub/GitLab UI.
- If a remote name is wrong, rename it:

  ```bash
  git remote rename <wrong-name> upstream   # or: origin
  ```

  Scripts enforce `upstream` for the org remote and `origin` for your fork.

---

### 2. Missing required tool

**Symptom:** `command not found` or `[MISSING]` output in the preflight check.

**Diagnosis:** the preflight loop in [Phase 0.1](#phase-0--pre-flight-checks)
lists missing tools explicitly.

**Fix:** install the missing tool for your platform. Common examples:

| Tool | Installation |
|------|-------------|
| `gh` | https://cli.github.com |
| `glab` | https://gitlab.com/gitlab-org/cli |
| `yq` (mikefarah) | `brew install yq` / `snap install yq` |
| `kustomize` | https://kubectl.docs.kubernetes.io/installation/kustomize/ |
| `oc` | https://console.redhat.com/openshift/downloads |
| `uv` | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |

After installing, re-run the preflight check before continuing.

---

### 3. RPM repo not yet available

**Symptom:** the polling loop in Phase 4 keeps returning HTTP 404 or the URL is
unreachable.

**Diagnosis:**

```bash
curl -v "$RPM_CHECK_URL"
```

- HTTP 404 → the URL path is wrong. Double-check `RPM_CHECK_URL` in
  `releases/foreman/$VERSION/settings`. Common mistakes: wrong el version (el9 vs
  el8), wrong architecture, typo in version number.
- HTTP 403 → CDN transient error; retry in a minute.
- Connection refused / DNS failure → network issue; check connectivity.

**Fix:**

- For a wrong URL: correct `RPM_CHECK_URL` in the settings file.
- To skip the RPM gate during testing:

  ```bash
  uv run hack/branch-release/branch_konflux --version=$VERSION --step=branch-tenants --skip-rpm-check
  ```

  Do not merge the tenants-config MR until RPMs are genuinely available.

---

### 4. kustomize validation failure

**Symptom:** `kustomize build` in [Phase 5.3](#53-validate-the-kustomize-build)
exits non-zero or produces an error message.

**Diagnosis:** run `kustomize build` with verbose output:

```bash
kustomize build $TENANT/foreman/components/$VERSION 2>&1
```

Common causes:
- YAML indentation error in a generated file.
- Missing `resources:` entry in a parent `kustomization.yaml`.
- A reference to `../base` that does not exist in that project's overlay path.

**Fix:**

1. Review the error message — `kustomize` typically identifies the file and line.
2. Open the file in an editor and correct the YAML.
3. Re-run `kustomize build` until it passes with zero errors.
4. Commit the fix (`git commit -m "Fix kustomize YAML"`) and push normally —
   do not force-push:

   ```bash
   git push origin branch-$BRANCH_NAME
   ```

   The MR updates automatically.

---

### 5. PR/MR already exists

**Symptom:** `gh pr create` or `glab mr create` fails with `already exists` or
`409 Conflict`.

**Diagnosis:**

```bash
# Find existing GitHub PR
gh pr list --repo theforeman/foreman-oci-images --head $GITHUB_USER:$BRANCH_NAME

# Find existing GitLab MR
glab mr list --repo fedora/infrastructure/konflux/tenants-config \
  --source-branch branch-$BRANCH_NAME --hostname gitlab.com
```

**Fix:**

- If the PR/MR is open and correct, you do not need to recreate it. Retrieve
  the existing URL and continue with the [Merge sequence](#phase-6--merge-sequence).
- If the PR/MR is open but has wrong content, push a fixup commit to the branch —
  the PR/MR updates automatically.
- If the PR/MR was closed and must be recreated:

  ```bash
  # GitHub: reopen or create against the same branch
  gh pr reopen <PR-NUMBER> --repo theforeman/foreman-oci-images

  # GitLab: reopen
  glab mr reopen <MR-IID> --repo fedora/infrastructure/konflux/tenants-config \
    --hostname gitlab.com
  ```

**Note:** if the upstream branch already exists (`git ls-remote upstream` shows
it), do **not** delete it. OCI image branches are permanent — see the
[Recovery](../CLAUDE.md#recovery) section in CLAUDE.md for the correct procedure.
