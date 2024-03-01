DS ?= swing_1
ROOT_DIR:=$(shell dirname $(realpath $(firstword $(MAKEFILE_LIST))))

test: build
	@rm -rf $(DS)-master
	@curl -sL https://gitlab.com/dilla-io/ds/$(DS)/-/archive/master/$(DS)-master.tar.gz | tar -xz
	@docker run -t -v $(ROOT_DIR)/$(DS)-master:/data/ validator definitions
	@docker run -t -v $(ROOT_DIR)/$(DS)-master:/data/ validator templates

run:
	- docker run -t -v $(ROOT_DIR)/$(DS)-master:/data/ validator run

build:
	- docker build -t validator --rm .

lint:
	- prettier --write README.md
	- prettier --write *.json
	- ruff check *.py
	- ruff format *.py
	- mypy --strict *.py
	- radon cc *.py -nc -s
	- flake8 --select D102 *.py
