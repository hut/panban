test:
	@set -e; \
	for FILE in $(shell grep -IHm 1 doctest -r panban | cut -d: -f1); do \
		echo "Testing $$FILE..."; \
		python $$FILE --doctest; \
	done

.PHONY: test
