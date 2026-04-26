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

## Secrets — for CD Workflow
Settings → Secrets and variables → Actions → New repository secret

| Secret Name           | Value |
|-----------------------|-------|
| AWS_ACCESS_KEY_ID     | AWS access key that has SSM, S3, and CloudFront permissions |
| AWS_SECRET_ACCESS_KEY | Corresponding secret key |
| AWS_REGION            | e.g., us-east-1 |

These are the same AWS credentials you use locally for deploy.sh.
Consider creating a dedicated IAM user for GitHub Actions with only the
permissions deploy.sh needs: SSM SendCommand, S3 PutObject/GetObject,
CloudFront CreateInvalidation.

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
