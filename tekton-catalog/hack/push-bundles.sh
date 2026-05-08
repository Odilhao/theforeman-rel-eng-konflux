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

  echo "==> Pushing ${repo}:latest"
  digest=$(echo "${yaml}" | tkn bundle push "${repo}:latest" -f - 2>&1 | grep -o 'sha256:[a-f0-9]*')

  echo "==> Published ${repo}:${sha} and ${repo}:latest@${digest}"
}

push_bundle pipeline-push-to-external-registry tekton-catalog/pipelines/push-to-external-registry
