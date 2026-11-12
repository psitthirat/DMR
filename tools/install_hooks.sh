#!/bin/sh
# Install the pre-commit check into this clone's .git/hooks (run once per clone).
set -e
cd "$(dirname "$0")/.."
cat > .git/hooks/pre-commit <<'HOOK'
#!/bin/sh
exec python3 tools/precommit_check.py --staged
HOOK
chmod +x .git/hooks/pre-commit
echo "pre-commit hook installed"
