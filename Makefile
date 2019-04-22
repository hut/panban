alltest: test lint

test:
	@set -e; \
	for FILE in $(shell grep -IHm 1 doctest -r panban | cut -d: -f1); do \
		echo "Testing $$FILE..."; \
		PYTHONPATH=".:"$$PYTHONPATH python3 $$FILE --doctest; \
	done

lint:
	@pylint3 -E panban

.PHONY: test lint alltest
