# Changelog

All notable changes are documented here. The project follows Semantic
Versioning after its first tagged release.

## Unreleased

- Bind the committed v0.1.0 evidence content address and release semantics to an
  executable verifier and regression tests.
- Keep release reproduction outputs outside the tracked canonical evidence
  directory.

## 0.1.0 - 2026-07-13

- Narrowed the supported surface to the local CLI/library runtime.
- Removed non-running API/worker services and unconnected dashboards from the
  default Compose topology.
- Added persistent finalization-conflict accounting distinct from terminal-event
  invariant violations.
- Added explicit, local-only destructive reset controls.
- Added Apache-2.0 licensing and bounded contribution/security surfaces.
- Published a content-addressed local smoke evidence bundle for the exact
  release candidate revision.
