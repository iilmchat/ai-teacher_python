.PHONY: gates-fast gates-full release-check

# S37-005: единый локальный прогон гейтов (см. docs/CI.md §15).
# На Windows без make используйте scripts/ci/gates.ps1.

gates-fast:
	bash scripts/ci/gates.sh --fast

gates-full:
	bash scripts/ci/gates.sh --full --ci

release-check: gates-full
