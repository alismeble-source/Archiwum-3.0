## Summary
- What changed:
- Why:

## Scope
- [ ] Mail pipeline
- [ ] Telegram dashboard
- [ ] Finance/quotes/payables logic
- [ ] Docs/config only

## Safety checklist
- [ ] No secrets/tokens/credentials added
- [ ] No large business data folders added
- [ ] `git status` clean after commit
- [ ] Local smoke check passed (python compile + ps1 parse)

## Validation
- Commands run:
```powershell
python -m py_compile 99_SYSTEM/_SCRIPTS/FINANCE/telegram_dashboard_bot_v2.py
```

- Result:

## Rollback
- Revert commit:
```bash
git revert <commit_sha>
```
