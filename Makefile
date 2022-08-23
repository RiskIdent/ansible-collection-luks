# SPDX-FileCopyrightText: 2022 Risk.Ident GmbH <contact@riskident.com>
#
# SPDX-License-Identifier: CC0-1.0

VERSION=$(shell grep '^version:' galaxy.yml | grep -o '[0-9\.]*')

.PHONY: build
build: riskident-luks-${VERSION}.tar.gz

riskident-luks-${VERSION}.tar.gz: galaxy.yml roles/** plugins/** docs/**
	@echo "Building ${VERSION}"
	ansible-galaxy collection build --force

.PHONY: clean
clean:
	rm -rfv riskident-luks-*.tar.gz

.PHONY: deps
deps: deps-pip deps-npm

.PHONY: deps-pip
deps-pip:
	pip install --user yamllint ansible-lint reuse

.PHONY: deps-npm
deps-npm: node_modules

node_modules:
	npm install

.PHONY: lint
lint: lint-md lint-yaml lint-ansible lint-license

.PHONY: lint-fix
lint-fix: lint-md-fix

.PHONY: lint-md
lint-md: node_modules
	npx remark . .github

.PHONY: lint-md-fix
lint-md-fix: node_modules
	npx remark . -o

.PHONY: lint-yaml
lint-yaml:
	yamllint .

.PHONY: lint-ansible
lint-ansible:
	ansible-lint roles

.PHONY: lint-license
lint-license:
	reuse lint
