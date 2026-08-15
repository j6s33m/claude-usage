# Legacy YAML package

`claude_usage.yaml` is the original package-based version of this project, kept
here for reference and for anyone who cannot use HACS.

**Do not run this at the same time as the integration.** Both create entities
with the same names. Loading both gives you duplicate entities with `_2`
suffixes and unpredictable results.

If you are migrating, delete `/config/packages/claude_usage.yaml` first, then
install the integration. See the migration section in the top-level
[README](../README.md).

This file is no longer maintained. It will be removed after the 2.1.0 release.
