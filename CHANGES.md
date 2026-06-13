# Pending Changes

## Summary

Security hardening and a privilege fix from a review of the scaffold template.

### dependabot-automerge.yml

- **Branch filter**: Added `branches: [main]` to `pull_request_target` trigger. Without this, fresh forks without branch protection would automerge immediately on PR open, before tests run.
- **Same-repo guard**: Added `github.event.pull_request.head.repo.full_name == github.repository` to the `if` condition. Defense-in-depth alongside the `dependabot[bot]` actor check, since `pull_request_target` runs with write tokens.
- **SHA-pinned action**: Pinned `fastify/github-action-merge-dependabot` from `@v3` (mutable tag) to `@d1b52cc4c7e618b19de8a43c7138213b277e820c`. The job holds `contents: write` and `pull-requests: write`, so a compromised upstream tag could inject code with those permissions.

### setup.sh

- **sudo corepack enable**: System Node.js path requires root to modify. Without `sudo`, `corepack enable` fails silently or errors depending on the container image.

## Diff

```diff
diff --git a/.devcontainer/setup.sh b/.devcontainer/setup.sh
index 09e84b2..fa8f2cb 100644
--- a/.devcontainer/setup.sh
+++ b/.devcontainer/setup.sh
@@ -3,7 +3,7 @@
 echo "Setting up development environment..."
 
 # Enable pnpm via corepack (ships with Node.js)
-corepack enable
+sudo corepack enable
 
 # Install Node.js dependencies from all package.json files
 while IFS= read -r -d '' pkg_file; do
diff --git a/.github/workflows/dependabot-automerge.yml b/.github/workflows/dependabot-automerge.yml
index 285da27..365bfbd 100644
--- a/.github/workflows/dependabot-automerge.yml
+++ b/.github/workflows/dependabot-automerge.yml
@@ -1,16 +1,18 @@
 name: Dependabot Automerge
 
-on: pull_request_target
+on:
+  pull_request_target:
+    branches: [main]
 
 jobs:
   automerge:
     runs-on: ubuntu-latest
-    if: github.actor == 'dependabot[bot]'
+    if: github.actor == 'dependabot[bot]' && github.event.pull_request.head.repo.full_name == github.repository
     permissions:
       contents: write
       pull-requests: write
     steps:
-      - uses: fastify/github-action-merge-dependabot@v3
+      - uses: fastify/github-action-merge-dependabot@d1b52cc4c7e618b19de8a43c7138213b277e820c # v3
         with:
           target: minor
           merge-method: squash
```
