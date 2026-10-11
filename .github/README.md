# Clean-install CI

`workflows/ci.yml` runs on every PR (including drafts), pushes to `main`, manual
dispatch, and merge-group checks. PR runs test the merge commit selected by
GitHub's normal checkout behavior. Superseded runs for the same PR are cancelled.
Adding the merge-group trigger does not enable a merge queue.

See [local validation results](validation.md) for completed checks and the remaining
GitHub rollout work.

## Required checks

| Job | Installation | Checks |
| --- | --- | --- |
| Workflow and layout | Verified actionlint 1.7.12; no application dependencies | All workflow files; tracked source layout |
| Backend quality | Python 3.12.14; core + `quality` group | Spelling, Ruff lint/format, basedpyright |
| Backend tests | Python matrix; core + `test` group | Offline pytest regression suite |
| Backend package | Digest-pinned Python/uv Docker images | Core dependency smoke and installed wheel smoke |
| Frontend | Node from `.nvmrc`; exact npm from `packageManager`; `npm ci` | ESLint, existing TypeScript scope, Vitest, Vite build |
| Browser | Python 3.12.14 core; frontend; Chromium headless shell | Scripted providers, loopback traffic, disposable storage |
| Required CI | Standard-library result check | Every expected upstream job must report `success` |

`ci-matrix.json` is the shared source for the regression/package matrix and local
package runner. It covers Python 3.11.16, 3.12.14, and 3.13.15. The package runner
forces the Docker install/check stages to execute and runs both runtime containers
with `--network none`. Core checks assert that local embedding and development
packages are absent. Optional local embeddings remain a manual smoke target.

Python locked installs reject stale lockfiles. Frontend jobs compare dependency
declarations with the lockfile's root metadata before running `npm ci`: npm can
otherwise accept a new direct dependency already locked transitively. PEP 517 build tools
and their complete dependency closure are pinned separately in `build-system.requires`;
their versions are not controlled by the project dependency lock. A lock refresh
should preserve existing compatible dependency versions unless an upgrade is intended.

Ruff checks include the backend, developer tools, backend tests, smoke harnesses,
and browser backend fixture. basedpyright keeps its existing source coverage and
warning policy. The frontend retains `checkJs: false`; TS/TSX errors still fail
its type-check command.

## Caches, timing, and diagnostics

Cache only downloaded dependencies; never restore installed environments or build
outputs. Cache keys include dependency manifests, lockfiles, and runtime/tool pins.
Remove local `rag` build cache entries before installation and before saving the
uv dependency cache. Package jobs use download-cache mounts within their fresh
Buildx builders and do not export cached installation/check layers.

Dispatch `CI` with `clean_install=true` to bypass persistent uv/npm caches. Otherwise,
cache restores are allowed but installations and checks still execute. The workflow
and layout check precedes parallel application jobs. Matrix jobs retain all results
with `fail-fast: false`. Aim for approximately 10 minutes with warm caches; record
cold and warm hosted timings before declaring that target achieved.

Failures retain available JUnit reports, command logs, browser traces/screenshots,
and application server logs for seven days. Successful builds are not uploaded.
Actions summaries record runtime versions and the aggregate job results. Job
timeouts bound workflow validation to 5 minutes, quality/tests/frontend to 10,
package/browser to 20, and aggregation to 2.

## Secret isolation

The workflow requests only `contents: read`, disables persisted checkout credentials,
and pins external actions to upstream commit SHAs. It uses `pull_request`, references
no production secrets or deployment environments, and grants no write or OIDC
permissions. Fork PRs do not receive repository secrets. GitHub may require a
maintainer to approve running a first-time contributor's workflow.

Providers are scripted or deterministic, storage is temporary, backend regression
tests deny network connections, browser traffic is restricted to fixture endpoints,
and smoke runtime containers have no external network. Downloads are permitted
during dependency/browser installation, not during application test execution.

## Local reproduction

Prepare the documented root developer environment and frontend dependencies, then
run `uv run --no-sync python -m devtools.check`. The command verifies tool versions
and runs every check family; pytest uses the active supported Python interpreter,
while package smoke tests use the entire pinned matrix. It returns nonzero and names
the failed stage. It does not install dependencies, apply fixes, or change locks.

Individual standard-library helpers are:

```bash
python3 -m devtools.ci layout
python3 -m devtools.ci frontend-lock
python3 -m devtools.ci matrix
python3 -m devtools.ci package --python 3.12 --log-dir /tmp/rag-smoke-logs
```

## One-time failure validation

Use disposable clean checkout copies or temporary PR validation commits; remove all
injected failures before the final successful run. Do not add deliberate failures
or permanent negative-test runs to normal CI.

| Fixture | Expected failure |
| --- | --- |
| Satisfiable dependency declaration changed without its lock update | `uv sync --locked` / frontend lock guard + `npm ci`; lock bytes unchanged |
| Undefined Python/JS name, unformatted Python, incompatible typed assignment | Lint, format, or type command |
| Failing pytest/Vitest/Playwright assertion | Corresponding test command and required gate |
| Import a missing frontend module | Production build |
| Exclude an existing backend source module from the wheel | Archive inspection or installed runtime |
| Track a legacy root application file or remove a required manifest | Layout guard |
| Add an invalid workflow expression | actionlint |
| Required job result is failed, skipped, cancelled, or missing | `devtools.ci required` rejects it |

Also check the local runner reports command failures, and verify a cache-disabled
successful run leaves tracked files and lockfiles unchanged. The aggregate helper
reads the actual `needs` results through `CI_RESULTS`; no synthetic results or
failure-injection switches are available in the hosted workflow.

## GitHub rollout

Repository implementation and local validation do not activate merge protection.
Hosted CI, fork behavior, cancellation, warm/cold timings, and merge blocking must
be validated with authenticated GitHub access. Keep rollout pending until those
checks have been exercised and the `Required CI` context is available.

1. Publish the PR and validate controlled failures and a restored successful run.
2. After the workflow reaches `main`, manually dispatch cache-disabled and warm runs.
3. Import `main-ruleset.json` in Settings → Rules → Rulesets, or create it through
   the API with an authenticated repository administrator:

   ```bash
   gh api --method POST repos/nehalvaghasiya/agentic-rag/rulesets \
     --input .github/main-ruleset.json
   ```

4. Verify the active ruleset targets `refs/heads/main`, requires `Required CI` from
   the GitHub Actions app (ID 15368), requires an up-to-date branch, and has no bypass
   actors. It also requires PRs without introducing a reviewer-count requirement.
   Retain existing independent protection rules; do not replace them.
5. Confirm a failed or cancelled PR cannot merge, administrators have no configured
   bypass, an out-of-date branch requires updating, and a fork PR runs without
   production secrets. Record the ruleset ID and hosted validation results.

To inspect the rules after creation:

```bash
gh api repos/nehalvaghasiya/agentic-rag/rulesets
gh api repos/nehalvaghasiya/agentic-rag/rulesets/RULESET_ID
```

The configuration supports a future merge queue; it does not enable one or add
deployment/release jobs.
