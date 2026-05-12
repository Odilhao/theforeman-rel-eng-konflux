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

  local min_version
  min_version=$(echo "${built}" | python3 -c \
    "import sys, yaml; d = yaml.safe_load(sys.stdin); \
     print(d['metadata']['annotations']['tekton.dev/pipelines.minVersion'])")

  echo "==> Building ${name} (minVersion=${min_version})"

  echo "==> Pushing ${repo}:${min_version}"
  echo "${built}" | tkn bundle push "${repo}:${min_version}" -f -

  echo "==> Tagging ${repo}:latest"
  skopeo copy "docker://${repo}:${min_version}" "docker://${repo}:latest"

  echo "==> Published ${repo}:${min_version} and ${repo}:latest"
}

push_bundle pipeline-push-to-external-registry tekton-catalog/pipelines/push-to-external-registry
push_bundle task-buildah-oci-ta tekton-catalog/tasks/buildah-oci-ta
