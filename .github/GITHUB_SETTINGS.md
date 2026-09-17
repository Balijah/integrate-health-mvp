# GitHub Repository Settings — Integrate Health

Manual settings to configure in GitHub UI (Settings tab on the repo).
These cannot be set via files.

---

## Branch Protection — `main`
Settings → Branches → Add rule → Branch name pattern: `main`

- [x] Require status checks to pass before merging
- [x] Require branches to be up to date before merging
- Status checks to require (appear after first CI run):
  - `Backend (Python)`
  - `Frontend (TypeScript + Build)`
  - `Secret Scan`
- [x] Do not allow force pushes
- [x] Do not allow deletions
- [x] Require conversation resolution before merging

---

## AWS Authentication — OIDC

The CD workflow uses GitHub OIDC to assume this short-lived AWS role:

`arn:aws:iam::317440775804:role/IntegrateHealthGitHubActionsDeploy`

The role trust policy only accepts tokens from this repository's protected
`production` environment. No long-lived AWS access keys are stored in GitHub.

---

## Environments — Production Gate
Settings → Environments → New environment: `production`

- [x] Required reviewers: add yourself (Burhan)
  This pauses the CD workflow for manual approval before deploying.
  You get an email — click Approve in GitHub to proceed.
- [x] Deployment branches: Selected branches → `main` only

---

## General Settings
Settings → General → Pull Requests:
- [x] Allow squash merging
- [ ] Allow merge commits (disable)
- [x] Allow rebase merging
- [x] Automatically delete head branches

---

## Dependabot Alerts
Settings → Security → Enable:
- [x] Dependency graph
- [x] Dependabot alerts
- [x] Dependabot security updates
