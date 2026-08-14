# INST-50E — Release / Bootstrap Integration

**Date:** 2026-08-14  
**Contract:** `AGENTS/INST-client-installer-scaffolding.md`  
**Prior stage:** `INST-50D-client-status.md`  
**Scope:** `trial-install.sh` release coherence and verified remote bootstrap only

---

## Real VM Finding (7402)

A clean Ubuntu VM attempted the production remote bootstrap with default `EIGHTBALL_RELEASE=v0.8.0`.

Observed result:

- VM networking, DNS, HTTPS, and `raw.githubusercontent.com` all worked.
- `curl` received **HTTP 404** for release URLs under `.../terminal-glass/8-ball/v0.8.0/...`.

**Root cause:** the immutable git tag `v0.8.0` is **not published** on GitHub. PR55 defines the release bundle in-repo, but customer bootstrap requires a published tag/ref that raw GitHub can serve.

**Secondary defect found:** `install/ubuntu/trial-install.sh` previously sourced `install/shared/8ball-version.sh` and `install/shared/8ball-release.sh` before any download step. A clean host with only `trial-install.sh` could not start bootstrap at all (chicken-and-egg), even after tag publication.

**Tertiary defect fixed:** `eightball_fetch_release_manifest()` in `8ball-release.sh` used `|| true` on the local-manifest lookup, so a clean host with no local `../releases/<tag>/manifest.json` entered the copy branch with an empty path instead of falling through to remote fetch.

---

## Release Publication Lifecycle

PR55 does **not** auto-publish tags. There is no GitHub Actions release workflow in this repository.

Required maintainer sequence after PR55 merges to `main`:

1. Ensure release artifacts are current on `main`:
   ```bash
   bash scripts/generate-release-manifest.sh v0.8.0
   git add install/releases/v0.8.0/
   git commit -m "Regenerate v0.8.0 release manifest"
   ```
2. Create an **immutable git tag** on the commit that contains the PR55 runtime bundle:
   ```bash
   git tag -a v0.8.0 <release-commit-sha> -m "8-BALL installer/runtime release v0.8.0"
   git push origin v0.8.0
   ```
3. Optionally create a GitHub Release from that tag (metadata only; raw bootstrap uses the tag ref).

Customer bootstrap must resolve from the **tag**, not from a Cursor feature branch and not from mutable `main`.

Verification after publication:

```bash
curl -fsSI https://raw.githubusercontent.com/terminal-glass/8-ball/v0.8.0/install/releases/v0.8.0/manifest.json
# expect HTTP/2 200
```

---

## Release Identity Mechanism

Production installs default to `EIGHTBALL_RELEASE=v0.8.0` and resolve **one** manifest:

```text
install/releases/v0.8.0/manifest.json
```

Remote URL after tag publication:

```text
https://raw.githubusercontent.com/terminal-glass/8-ball/v0.8.0/install/releases/v0.8.0/manifest.json
```

The manifest lists 121 repo-relative artifacts under a single `release_tag` and `repository` (`terminal-glass/8-ball`).

---

## Customer Bootstrap Entrypoint

### Intended one-line customer command (after `v0.8.0` tag is published)

```bash
curl -fsSL https://raw.githubusercontent.com/terminal-glass/8-ball/v0.8.0/install/ubuntu/trial-install.sh -o trial-install.sh && sudo bash trial-install.sh
```

This is a **single downloaded entrypoint file**. It must not require a repository checkout.

### Bootstrap sequence on a clean host

```text
customer downloads install/ubuntu/trial-install.sh only
        ↓
entrypoint bootstrap (inline in trial-install.sh)
  fetch manifest from published tag
  verify + install install/shared/8ball-version.sh
  verify + install install/shared/8ball-release.sh
        ↓
source shared helpers
        ↓
eightball_bootstrap_release_runtime()
  verify trial-install.sh
  download + verify full runtime bundle from same manifest
        ↓
8.1 → 8.2 → 8.3
```

Entrypoint bootstrap is implemented inline in `install/ubuntu/trial-install.sh` so shared helpers are acquired before `source`.

---

## Profile / Runtime Delivery Mechanism

Runtime bundle contract: `install/releases/v0.8.0/runtime-bundle.json`

Pinned subset (not the full 72k matrix):

- Ubuntu installer scripts + shared helpers required by 8.1–8.3
- `scripts/c10_common.py`
- `AGENTS/data-science/profile-mapping/8ball-base-pilot-menu.json`
- Release-pinned `install/releases/v0.8.0/install-manifest.json`
- `profiles/lanes.json`, `profiles/manifest.json`, ubuntu provider assumptions
- Profile runtime for `qwen3` and `tinyllama` across `ubuntu/cpu` and `ubuntu/cuda`

Bootstrap stages artifacts under:

```text
${PHILOSOPHER_ROOT}/.8ball-release/${EIGHTBALL_RELEASE}/
```

and exports `EIGHTBALL_REPO_ROOT` and `EIGHTBALL_MANIFEST` from that same release context.

---

## Checksum Mechanism

Flow:

```text
resolve release
    → obtain manifest
    → download artifact to file
    → SHA-256 verify
    → install / execute
```

Checksum verification is fail-closed. Components are downloaded with `curl -o` then verified; no `curl | bash`.

---

## Development / Local Behavior

| Override | Effect |
| --- | --- |
| Full local checkout | `eightball_local_bundle_ready` → no remote bootstrap |
| `EIGHTBALL_REPO_ROOT` | Use supplied tree |
| `EIGHTBALL_RELEASE=main` | Development raw URLs for entrypoint helpers only |
| `EIGHTBALL_RAW_BASE` | Explicit HTTPS script base |
| `EIGHTBALL_ALLOW_UNVERIFIED_DOWNLOADS=1` | Skip verified bootstrap |

Development overrides are explicit and must not become the production default.

---

## Tests / Results

| Check | Result |
| --- | --- |
| `pytest tests/test_inst_50e_release_integrity.py` | PASS (includes clean-entrypoint bootstrap tests) |
| Full `pytest` | PASS (416 passed) |

New tests cover:

- empty directory + only `trial-install.sh` + mock immutable release → shared helpers acquired
- same entrypoint → full runtime bundle staged
- unpublished tag → fail-closed manifest error

---

## Before Retrying VM 7402

1. Merge PR55 to `main`.
2. Regenerate and commit `install/releases/v0.8.0/manifest.json` if needed.
3. Publish git tag `v0.8.0` pointing at that release commit.
4. Verify raw manifest URL returns HTTP 200.
5. Re-run the one-line customer bootstrap command above on VM 7402.

INST-50F (Proxmox matrix) is **not** started in this stage.
