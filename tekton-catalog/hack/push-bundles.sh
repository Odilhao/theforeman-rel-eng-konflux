#!/usr/bin/env bash
# Local helper for testing bundle builds. Authoritative publishing is done
# by the publish-pipeline-bundle GitHub Actions workflow on push to develop.
set -euo pipefail

REGISTRY=${REGISTRY:-quay.io/foreman/tekton-catalog}

push_bundle() {
  local name=$1
  local src=$2
  local repo="${REGISTRY}/${name}"
  local built
  built=$(kustomize build "${src}")

  # Tasks carry app.kubernetes.io/version (e.g. 0.9.3); pipelines fall back
  # to tekton.dev/pipelines.minVersion (e.g. 0.12.1).
  local full_version
  full_version=$(echo "${built}" | python3 -c "
import sys, yaml
d = yaml.safe_load(sys.stdin)
version = (d['metadata'].get('labels', {}).get('app.kubernetes.io/version')
           or d['metadata']['annotations']['tekton.dev/pipelines.minVersion'])
print(version)")

  local minor_version
  minor_version=$(echo "${full_version}" | cut -d. -f1,2)

  echo "==> Building ${name} (version=${full_version})"

  echo "==> Pushing ${repo}:${full_version}"
  echo "${built}" | tkn bundle push "${repo}:${full_version}" -f -

  echo "==> Tagging ${repo}:${minor_version} and ${repo}:latest"
  skopeo copy "docker://${repo}:${full_version}" "docker://${repo}:${minor_version}"
  skopeo copy "docker://${repo}:${full_version}" "docker://${repo}:latest"

  echo "==> Published ${repo}:${full_version}, ${repo}:${minor_version} and ${repo}:latest"
}

push_bundle pipeline-push-to-external-registry tekton-catalog/pipelines/push-to-external-registry
push_bundle task-buildah-oci-ta tekton-catalog/tasks/buildah-oci-ta
