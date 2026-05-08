#!/usr/bin/env bash
set -euo pipefail

REGISTRY=${REGISTRY:-quay.io/foreman/tekton-catalog}

push_bundle() {
  local name=$1
  local src=$2
  local ref="${REGISTRY}/${name}:latest"

  echo "==> Building ${name}"
  local yaml
  yaml=$(kustomize build "${src}")

  echo "==> Pushing ${ref}"
  digest=$(echo "${yaml}" | tkn bundle push "${ref}" -f - 2>&1 | grep -o 'sha256:[a-f0-9]*')

  echo "==> Published ${ref}@${digest}"
}

push_bundle pipeline-push-to-external-registry tekton-catalog/pipelines/push-to-external-registry
