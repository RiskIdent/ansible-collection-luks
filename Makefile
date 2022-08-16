# SPDX-FileCopyrightText: 2022 Risk.Ident GmbH <contact@riskident.com>
#
# SPDX-License-Identifier: CC0-1.0

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

