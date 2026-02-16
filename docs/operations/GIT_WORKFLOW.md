# Git Workflow (Main + Dev)

## Branch roles
- `main`: stable production baseline.
- `dev`: active integration branch before merge to `main`.

## Daily flow
1. Work on `dev`.
2. Commit with clear message.
3. Push `dev`.
4. Merge to `main` only after smoke checks pass.

## Safe sync command
Use the repository helper:
```powershell
.\sync.ps1 "your message"
```

`sync.ps1` stages only safe code/doc paths and avoids `git add .`.

## Do not do
- Do not force-push `main` (`--force`) for routine work.
- Do not commit secrets from `99_SYSTEM/_SECRETS`.
- Do not commit live business data folders (`CASES`, `00_INBOX`, etc.).
