# Patched opencode web UI bundle

This directory contains a patched copy of the SPA that ships inside the
`sprisa/opencode:1.18.15` image. opencode's web client is compiled into the
binary, so it cannot be replaced by dropping files into a web root. Instead,
`charts/opencode` runs an nginx sidecar that intercepts exactly one asset path
(`/assets/index-DkiM3pJJ.js`) and serves this patched bundle.

## What the patch fixes

- Per-device home-session visibility: all devices see the same sessions.
- React Query auto-refetch on window focus / network reconnect, so status
  queries recover after mobile tab suspension.
- Immutable caching for hashed `/assets/` chunks and `no-store` on API
  responses, to avoid stale session state and lazy-import failures on flaky
  mobile connections.

## How it is deployed

1. The ArgoCD-managed init container clones this repo into the `workspace`
   PVC and copies `.ui/index-DkiM3pJJ.js` onto the git-immune `data` PVC
   (seed path in `charts/opencode/values.yaml`).
2. The nginx sidecar aliases `/assets/index-DkiM3pJJ.js` to
   `/data/.ui/index-DkiM3pJJ.js`, which is where the `data` PVC is mounted in
   the `ui` container.

Keeping the bundle on the `data` PVC means workspace git operations (branch
switches, checkouts) cannot delete it.

## Version coupling

The asset filename hash (`index-DkiM3pJJ.js`) is baked into the opencode build.
When bumping the image tag away from `1.18.15`, this bundle and the nginx
config must be regenerated from the new build's SPA; the readiness probe also
references the hashed path, so it must be updated in lockstep.
