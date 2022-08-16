
.PHONY: deps
deps: node_modules

node_modules:
	npm install

.PHONY: lint
lint: lint-md

.PHONY: lint-fix
lint-fix: lint-md-fix

.PHONY: lint-md
lint-md: node_modules
	npx remark .

.PHONY: lint-md-fix
lint-md-fix: node_modules
	npx remark . -o

