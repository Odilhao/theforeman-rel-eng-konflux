#!/usr/bin/env bash
set -euo pipefail

REGISTRY=${REGISTRY:-quay.io/foreman/tekton-catalog}

push_bundle() {
  local name=$1
  local src=$2
  local repo="${REGISTRY}/${name}"
  local sha
  sha=$(git rev-parse --short HEAD)

  echo "==> Building ${name}"
  local yaml
  yaml=$(kustomize build "${src}")

  echo "==> Pushing ${repo}:${sha}"
  echo "${yaml}" | tkn bundle push "${repo}:${sha}" -f -

  echo "==> Tagging ${repo}:latest"
  skopeo copy "docker://${repo}:${sha}" "docker://${repo}:latest"

  echo "==> Published ${repo}:${sha} and ${repo}:latest"
}

push_bundle pipeline-push-to-external-registry tekton-catalog/pipelines/push-to-external-registry
