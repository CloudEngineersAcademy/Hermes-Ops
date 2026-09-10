CHANGELOG
=========

Version 1.0.0 (2026-09-07)
----------------------------

### Added
- GitHub Actions CI workflow: lint (flake8, black, isort), secret scanning (gitleaks), saver integration test
- Secret redaction in transcript saver: GitHub PATs, bearer tokens, hex strings, AWS keys, private key headers
- Transcript integration: reads from ~/.hermes/state.db, incremental saves per session
- Scheduled save via cron (every 3 hours)
- .env + .gitignore for secret management

### Changed
- Saver script rewritten with full DB integration and redaction
- README updated with security section and full documentation

### Fixed
- Secret redaction patterns expanded to catch AWS access keys, private key headers, and generic hex tokens

### Known Limitations
- CI workflow uses mocked push (no real PAT in CI environment)
- Branch protection not yet configured on main
- No automated deploy step yet (CD phase pending)

---

Version 0.1.0 (2026-09-05)
----------------------------

### Added
- Initial repository setup
- README.md with purpose and structure
- Directory structure: sessions/, scripts/, configs/, notes/
- Session saver script (basic version)
- Cron wrapper for scheduled saves
- First session transcript saved
