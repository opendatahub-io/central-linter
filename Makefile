.PHONY: help linter-central linter-ruff-check linter-yamllint linter-renovate linter-mr-commit build push test clean

# Configuration
IMAGE_NAME := quay.io/aipcc-cicd/central-linter
IMAGE_TAG ?= latest
CONTAINERFILE := Containerfile
CONTEXT := .
CONTAINER_MANAGER ?= podman

# Linter configuration
RUFF_ARGS ?= check .
RUFF_CONFIG ?=

YAMLLINT_ARGS ?= .
YAMLLINT_CONFIG ?=

RENOVATE_VALIDATOR_ARGS ?=
RENOVATE_CONFIG ?=

help:
	@echo "Available targets:"
	@echo "  linter-central     - Run all linters (ruff, yamllint, renovate, mr-commit)"
	@echo "  linter-ruff-check  - Run only ruff check"
	@echo "  linter-yamllint    - Run only yamllint"
	@echo "  linter-renovate    - Run only renovate-config-validator"
	@echo "  linter-mr-commit   - Run only MR/commit linter"
	@echo "  build              - Build image for native architecture"
	@echo "  test               - Test the linters in the container"
	@echo "  push               - Push image to quay.io"
	@echo "  clean              - Remove local images"
	@echo ""
	@echo "Linter configuration (optional):"
	@echo "  RUFF_CONFIG=path       - Custom ruff config (e.g., --config .ci/ruff.toml)"
	@echo "  YAMLLINT_CONFIG=path   - Custom yamllint config (e.g., -c .ci/yamllint.yaml)"
	@echo "  RENOVATE_CONFIG=path   - Custom renovate file (default: auto-discovery)"

linter-central: linter-ruff-check linter-yamllint linter-renovate linter-mr-commit
	@echo ""
	@echo "All linters passed successfully"

linter-ruff-check:
	@echo ""
	@echo "================================================================================"
	@echo "Running ruff check..."
	@echo "================================================================================"
	@if [ -z "$(RUFF_CONFIG)" ]; then \
		if [ ! -f ".ruff.toml" ] && [ ! -f "ruff.toml" ] && [ ! -f "pyproject.toml" ]; then \
			if [ -f "$$HOME/.config/ruff.toml" ]; then \
				echo "Using shared ruff config from container..."; \
				ruff check --config $$HOME/.config/ruff.toml $(RUFF_ARGS) || (echo "ERROR: Ruff check failed" && exit 1); \
			else \
				ruff $(RUFF_ARGS) || (echo "ERROR: Ruff check failed" && exit 1); \
			fi; \
		else \
			ruff $(RUFF_ARGS) || (echo "ERROR: Ruff check failed" && exit 1); \
		fi; \
	else \
		ruff $(RUFF_CONFIG) $(RUFF_ARGS) || (echo "ERROR: Ruff check failed" && exit 1); \
	fi
	@echo "Ruff check passed"
	@echo ""

linter-yamllint:
	@echo ""
	@echo "================================================================================"
	@echo "Running yamllint..."
	@echo "================================================================================"
	@if [ -z "$(YAMLLINT_CONFIG)" ]; then \
		if [ ! -f ".yamllint" ] && [ ! -f ".yamllint.yaml" ] && [ ! -f ".yamllint.yml" ]; then \
			if [ -f "$$HOME/.config/yamllint.yaml" ]; then \
				echo "Using shared yamllint config from container..."; \
				yamllint -c $$HOME/.config/yamllint.yaml $(YAMLLINT_ARGS) || (echo "ERROR: YAML lint failed" && exit 1); \
			else \
				yamllint $(YAMLLINT_ARGS) || (echo "ERROR: YAML lint failed" && exit 1); \
			fi; \
		else \
			yamllint $(YAMLLINT_ARGS) || (echo "ERROR: YAML lint failed" && exit 1); \
		fi; \
	else \
		yamllint $(YAMLLINT_CONFIG) $(YAMLLINT_ARGS) || (echo "ERROR: YAML lint failed" && exit 1); \
	fi
	@echo "YAML lint passed"
	@echo ""

linter-renovate:
	@echo ""
	@echo "================================================================================"
	@echo "Running renovate-config-validator..."
	@echo "================================================================================"
	@if [ -f "$(RENOVATE_CONFIG)" ]; then \
		renovate-config-validator $(RENOVATE_VALIDATOR_ARGS) $(RENOVATE_CONFIG) || (echo "ERROR: Renovate config validation failed" && exit 1); \
	else \
		renovate-config-validator $(RENOVATE_VALIDATOR_ARGS) || (echo "ERROR: Renovate config validation failed" && exit 1); \
	fi
	@echo "Renovate config validation passed"
	@echo ""

linter-mr-commit:
	@echo ""
	@echo "================================================================================"
	@echo "Running MR/commit linter..."
	@echo "================================================================================"
	@python3 $$HOME/.scripts/mr_commit_linter.py || (echo "ERROR: MR/commit linter failed" && exit 1)
	@echo "MR/commit linter passed"
	@echo ""

build:
	@echo "Building image for native architecture..."
	$(CONTAINER_MANAGER) build \
		-t $(IMAGE_NAME):$(IMAGE_TAG) \
		-f $(CONTAINERFILE) $(CONTEXT)
	@echo "Build complete: $(IMAGE_NAME):$(IMAGE_TAG)"

test:
	@echo "Testing central-linter image..."
	@echo "Testing ruff..."
	$(CONTAINER_MANAGER) run --rm $(IMAGE_NAME):$(IMAGE_TAG) ruff --version
	@echo "Testing yamllint..."
	$(CONTAINER_MANAGER) run --rm $(IMAGE_NAME):$(IMAGE_TAG) yamllint --version
	@echo "Testing renovate-config-validator..."
	$(CONTAINER_MANAGER) run --rm $(IMAGE_NAME):$(IMAGE_TAG) renovate-config-validator
	@echo "All linters are functional"

push:
	@echo "Pushing image: $(IMAGE_NAME):$(IMAGE_TAG)..."
	$(CONTAINER_MANAGER) push $(IMAGE_NAME):$(IMAGE_TAG)
	@echo "Successfully pushed: $(IMAGE_NAME):$(IMAGE_TAG)"

clean:
	@echo "Removing local central-linter images..."
	$(CONTAINER_MANAGER) rmi $(IMAGE_NAME):$(IMAGE_TAG) 2>/dev/null || true
	@echo "Cleanup complete"
