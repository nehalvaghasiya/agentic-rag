# Local Picomatch security fork

This private, MIT-licensed copy is based on the unmodified `picomatch@4.0.7`
npm runtime. `upstream-sha256.json` records the original runtime/license hashes.
The original copyright and license are retained in `LICENSE`.

## Why it exists

As checked on 2026-11-17, npm's latest published Picomatch is 4.0.7 and is
covered by [GHSA-fc5q-39xc-vjpf / CVE-2026-112366](https://github.com/advisories/GHSA-fc5q-39xc-vjpf).
All supported Vite/Vitest versions used by this project depend on Picomatch.
The [upstream release request](https://github.com/micromatch/picomatch/issues/247)
is open. [Proposed upstream patch #238](https://github.com/micromatch/picomatch/pull/238)
(commit `44f192261f312ddf236cb7bdc05d8f22663f98f9`) explains the missing
single-branch analysis, but is not merged or published.

Our small change to `lib/parse.js` conservatively literalizes repeated extglobs
whose branches contain an unescaped, unquoted glob `*` outside a character class.
This covers the reported `+(*a)` and `+(*)` forms and also anchored-prefix forms
such as `+(a*)b`, which can still backtrack when a later suffix fails. Quoted and
escaped stars, character classes, ordinary globs, literal extglob alternatives,
and the existing safe character-class reductions remain supported. The guard
cannot be disabled with `maxExtglobRecursion: false`.

The fork has a distinct private package name, `@agentic-rag/picomatch`, and keeps
version 4.0.7 for consumers' major-version compatibility. It is **not** an
upstream patched release. The root npm override installs it under the expected
`picomatch` module name for every consumer. A direct file dependency anchors its
location and the override references that dependency using `$picomatch`, so
clean installs never resolve the file relative to a transitive package.
There are no install scripts or
additional dependencies.

## Verification and removal

Run `npm run test:security`. It checks every installed copy resolves to this
fork, tests ordinary matcher behavior, and runs malicious patterns in a child
process with a hard timeout. CI also runs the complete, development-inclusive
`npm audit`. npm does not assess local fork source: a clean registry audit is
supplemented by these explicit security regressions and source provenance.

When a reviewed upstream release fixes this advisory, remove the override and
this directory, update the lockfile, and adapt the security resolution check to
require that release. Keep the denial-of-service and compatibility regressions.
