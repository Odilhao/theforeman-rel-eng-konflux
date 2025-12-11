## Release Logic

### Nightly Releases

All projects are configured with automated nightly releases using Konflux ReleasePlans:

- **Auto-release**: Enabled via `release.appstudio.openshift.io/auto-release: "true"` label
- **Trigger**: Automatically releases on successful component builds
- **Target**: External Quay.io registry under `quay.io/theforeman/` organization
- **Tag**: `nightly`

### Projects with Nightly Releases

| Project | Component | Repository | Tag |
|---------|-----------|------------|-----|
| Candlepin | candlepin-develop | quay.io/theforeman/candlepin | nightly |
| Foreman | foreman-develop | quay.io/theforeman/foreman | nightly |
| Foreman | foreman-proxy-develop | quay.io/theforeman/foreman-proxy | nightly |
| Pulp | pulp-develop | quay.io/theforeman/pulp | nightly |
| Foreman MCP Server | foreman-mcp-server-develop | quay.io/theforeman/foreman-mcp-server | nightly |

### Point-in-Time Releases

Point-in-time releases will be created for stable versions and will be configured separately from nightly releases.

### Release Pipeline

Releases use the Konflux release-service-catalog pipeline:
- **Pipeline**: `push-to-external-registry`
- **Source**: https://github.com/konflux-ci/release-service-catalog.git
- **Branch**: production

### Reference

For more details on creating and managing ReleasePlans, see:
- [Konflux ReleasePlan Documentation](https://konflux-ci.dev/docs/releasing/create-release-plan/)

