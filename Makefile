.PHONY: test validate regenerate generate build check pdf package

# Explicit authoring operation: rewrites lesson snapshots and generated appendices.
# Ordinary builds intentionally preserve learner edits to code and Markdown.
regenerate:
	python3 scripts/build_lessons.py
	python3 scripts/build_traces.py

generate: regenerate

test:
	python3 -m unittest discover -s tests -v

validate:
	python3 scripts/validate.py
	python3 scripts/check_snippets.py
	python3 scripts/check_markdown.py

build: validate
	python3 scripts/build.py
	python3 scripts/check_site.py

check: test build
	python3 scripts/check_walkthroughs.py

# Optional local export only; not used by CI or copied into site/.
pdf: build
	python3 scripts/export_pdf.py

package: check
	python3 scripts/package.py
