# Deploying cinebox to PyPI

Publishing uses **Trusted Publishing (OIDC)** — no API token is stored in
GitHub. The `pypi` workflow signs in with a short-lived identity granted by a
trusted publisher configured on PyPI.

This must be done **once per project**; after that, releasing is just pushing a
tag and creating a GitHub Release.

## Prerequisites

- A [PyPI account](https://pypi.org/account/register/) with a verified email.
- A `hosam00/cinebox` GitHub repository with the `release.yml` workflow present.

## One-time setup

### 1. GitHub environment

1. Repo → **Settings → Environments → New environment**.
2. Name it exactly **`pypi`** (the workflow references this name).
3. Set the environment URL to `https://pypi.org/project/cinebox/`.

### 2. PyPI trusted publisher

The `cinebox` project already exists on PyPI, so add the publisher from the
project settings:

1. Open [your PyPI projects](https://pypi.org/manage/projects/), choose
   **cinebox**, then open **Publishing**.
2. Add a GitHub Actions trusted publisher with exactly:

   | Field            | Value             |
   |------------------|-------------------|
   | Owner            | `hosam00`         |
   | Repository       | `cinebox`         |
   | Workflow name    | `release.yml`     |
   | Environment name | `pypi`            |

   For a TestPyPI dry run, use a pending publisher under the TestPyPI tab and
   install test builds from `https://test.pypi.org/simple/`. See "Test runs"
   below.

3. Save. PyPI tells the workflow what to expect; GitHub can now mint publish
   tokens through OIDC.

> A brand-new PyPI project uses the **pending publisher** flow from your
> account page. Because `cinebox` is already published, configure the trusted
> publisher from the project's **Publishing** settings instead.

## Releasing

1. Update the version in `pyproject.toml` and move the changelog entries out of
   `## [Unreleased]`.
2. Update the lockfile and run the full local gate:

   ```bash
   uv lock
   uv sync --group dev --locked
   uv run ruff check src tests
   uv run ruff format --check src tests
   uv run pytest --cov=src/cinebox
   uv build
   ```

3. Smoke-test the built wheel:

   ```bash
   uv venv /tmp/cinebox-release-venv
   uv pip install --python /tmp/cinebox-release-venv/bin/python dist/*.whl
   /tmp/cinebox-release-venv/bin/cinebox --version
   ```

4. Commit and push the release changes to `main`, then wait for CI:

   ```bash
   git status
   git add <files>
   git commit -m "chore(release): v0.2.0"
   git push origin main
   ```

5. Tag the tested commit and push the tag. The tag must match the package
   version without the leading `v`; the release workflow enforces this.

   ```bash
   git tag v0.2.0
   git push origin v0.2.0
   ```

6. Create a GitHub Release **from that tag** (Draft → Publish). The
   `release: published` event triggers the workflow.
7. Watch **Actions → Publish to PyPI**. The publish step only runs for tag refs;
   `workflow_dispatch` builds and smoke-tests but does not publish.
8. Verify the published artifact:

   ```bash
   uvx --from "cinebox==0.2.0" cinebox --version
   uvx --from "cinebox==0.2.0" cinebox --help
   ```

## Notes

- The PyPI project name must equal the package name `cinebox` from
  `pyproject.toml`.
- The `environment: pypi` must exactly match the trusted publisher's environment
  name, or the OIDC exchange fails.
- Never reuse a version that already exists on PyPI. Bump the version before
  tagging.
- Manual `workflow_dispatch` runs build and wheel smoke tests only (the publish
  step is tag-gated) — use it to validate the workflow.

## Test runs (optional)

Point a temporary workflow at TestPyPI with
`https://test.pypi.org/legacy/` as the repository and
`https://test.pypi.org/project/cinebox/` as the environment URL. Create a
matching pending publisher under the TestPyPI tab of the Trusted Publishers
page. Install test builds with:

```bash
uvx --index-url https://test.pypi.org/simple/ \
  --extra-index-url https://pypi.org/simple/ \
  --from "cinebox==0.2.0" cinebox --version
```

After the first successful release you can remove the TestPyPI publisher or
keep it for practice runs.
