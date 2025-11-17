## The Foreman Release Engineering Konflux Artifacts

This repository contains YAML configuration files used to build, release, and maintain container images for [The Foreman](https://theforeman.org/) project using [Konflux](https://konflux.fedoraproject.org/).

### About Konflux

Konflux is an open-source CI/CD platform that provides secure software supply chain capabilities. The Foreman project uses Konflux to build container images with enhanced security through SLSA compliance, hermetic builds, and automated vulnerability scanning. For more details on this initiative, see the [RFC on evolving our container image builds](https://community.theforeman.org/t/rfc-evolving-our-container-image-builds/44990/).

### Prerequisites

To interact with the resources in this repository, you need:

1. A valid account in the [Fedora Account System (FAS)](https://accounts.fedoraproject.org/)
2. Access permissions configured in the [tenant-config RBAC settings](https://gitlab.com/fedora/infrastructure/konflux/tenants-config/-/blob/main/cluster/kfluxfedorap01/theforeman-org-tenant/rbac.yaml)

### Repository Structure

- **`project/`** - Contains project definitions for Konflux. Each project represents one [application](https://konflux-ci.dev/docs/building/creating/) with its own configuration and build rules.

- **`release/`** - Contains definitions for each [release](https://konflux-ci.dev/docs/releasing/create-release/) created at specific points in time.

### Getting Started

Follow these steps in order to get started with Konflux:

1. **Install the GitHub App** (required for onboarding GitHub repositories):
   - https://github.com/apps/konflux-fedora

2. **Access the Konflux UI** (use FAS authentication):
   - https://konflux.fedoraproject.org

3. **OpenShift Console** (alternative interface):
   - https://console-openshift-console.apps.kfluxfedorap01.toli.p1.openshiftapps.com

### Additional Resources

- **ArgoCD** - Used for deploying Konflux control plane and user configurations:
  - https://argocd-server-argocd.apps.kfluxfedorap01.toli.p1.openshiftapps.com/

- **Upstream Documentation** - General Konflux usage documentation:
  - https://konflux-ci.dev/docs/

- **Community Discussion** - RFC on The Foreman container builds:
  - https://community.theforeman.org/t/rfc-evolving-our-container-image-builds/44990/
