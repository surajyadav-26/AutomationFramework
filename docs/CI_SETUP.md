# CI setup (one time)

The workflows in `.github/workflows/` have been validated locally (YAML parses, every lint/test
command was run by hand) but they need a GitHub repository to run. Do this once.

## 1. Push the repository
```
git remote add origin https://github.com/<owner>/<repo>.git
git push -u origin main          # the local branch is already named main
```
`ci.yml` runs on pushes to `main` and on pull requests.

## 2. Add repository secrets
Settings → Secrets and variables → Actions → New repository secret:

| Secret | Value |
|---|---|
| `APP_PASSWORD` | the saucedemo password |
| `API_PASSWORD` | the dummyjson password |

## 3. Allow the baseline workflow to open pull requests
Settings → Actions → General → Workflow permissions → tick
**Allow GitHub Actions to create and approve pull requests** (and keep *Read and write permissions*).

## 4. Generate the linux visual baselines (CI is the source of truth)
1. Actions → **update-baselines** → Run workflow.
2. It opens a pull request named *Update linux visual baselines* with images under
   `baselines/linux/<browser>/1280x720/`.
3. Review every image by eye, then merge. Until this is merged, the `visual` job in `ci.yml` fails
   with "no baseline for ..." by design.

## 5. First green run
Open a pull request or push to `main`. Expected job order:
`lint` (ruff, import rules, check_rules, framework self-tests) → `api` → `ui-smoke` → `ui-full`
→ `visual` / `accessibility` / `cross-browser` (firefox, webkit).

## If something fails on the first run
- `no baseline for ...` in `visual`: step 4 is not merged yet.
- `APP_PASSWORD is not set`: step 2.
- Visual mismatch of a few percent only on linux: fonts differ from the local OS. Regenerate with
  step 4 and review; do not copy windows or macos images into `baselines/linux`.
- A dummyjson read timeout in `api`: the public service is occasionally slow. Re-run the job.
