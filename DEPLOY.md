# Deploying cinebox to PyPI

Publishing uses **Trusted Publishing (OIDC)** — no API token is stored in
GitHub. The `pypi` workflow signs in with a short-lived identity granted
by a pending publisher you create in your PyPI account.

This must be done **once per project**; after that, releasing is just
pushing a tag + creating a GitHub Release.

## Prerequisites

- A [PyPI account](https://pypi.org/account/register/) with a verified email.
- A `hosam00/cinebox` GitHub repo with the `release.yml` workflow present.

## One-time setup

### 1. GitHub environment

1. Repo → **Settings → Environments → New environment**.
2. Name it exactly **`pypi`** (the workflow references this name).
3. Set the environment URL to `https://pypi.org/project/cinebox/`.

### 2. PyPI pending publisher

1. Go to [PyPI Trusted Publishers](https://pypi.org/manage/account/publishing/).
2. **Add a new pending publisher** and fill in exactly:

   | Field            | Value                              |
   |------------------|------------------------------------|
   | Owner            | `hosam00`                          |
   | Repository       | `cinebox`                          |
   | Workflow name    | `Publish to PyPI` (must match the `name:` in `release.yml`) |
   | Environment name | `pypi`                             |

   (Optionally repeat with the TestPyPI tab to test against
   `pypi.org/simple/` first. See "Test runs" below.)

3. Save. PyPI tells it what to expect; GitHub now has permission to mint
   publish tokens via the workflow's OIDC identity.

## Releasing

1. Bump the version in `pyproject.toml`.
2. Sanity-check locally:

   ```bash
   uv sync --group dev
   uv run pytest
   uv build
   ```

3. Tag and push:

   ```bash
   git tag v0.1.0
   git push origin v0.1.0
   ```

4. Create a GitHub Release **from that tag** (Draft → Publish). The
   `release: published` event triggers the workflow.
5. Watch **Actions → Publish to PyPI**. The publish step only runs for
   tag refs; workflow_dispatch builds but does not publish.
6. Verify:

   ```bash
   pipx install cinebox
   uv tool run cinebox --help
   ```

## Notes

- The PyPI project name must equal the package name `cinebox` from
  `pyproject.toml`; the first release owns the name.
- The `environment: pypi` must exactly match the pending publisher's
  environment name or the OIDC exchange fails with "pending publisher
  not found".
- Manual workflow_dispatch runs build only (tag guard on the publish
  step) — use it to smoke-test `uv build` in CI.

## Test runs (optional)

Point a temporary workflow at TestPyPI with
`https://test.pypi.org/legacy/` as the repository and
`https://test.pypi.org/project/cinebox/` as the environment URL. Create a
matching pending publisher under the TestPyPI tab of the Trusted
Publishers page. After the first successful release you can remove it or
keep it for practice runs.