# Using ubi10/nodejs-22 as base image because Renovate requires Node.js 22
ARG BASE_IMAGE=registry.access.redhat.com/ubi10/nodejs-22:10.0-1762806356
FROM ${BASE_IMAGE}

ARG RUFF_VERSION=0.14.2
ARG YAMLLINT_VERSION=1.38.0
ARG RENOVATE_VERSION=43.5.0

# Ensure we're running as root for package installation
USER root

# Install system dependencies
RUN dnf install -y \
        python3 \
        python3-pip \
        git \
        make \
    && dnf clean all

# Install Python packages: linters, script dependencies, and testing tools
RUN pip3 install --no-cache-dir \
        # Python linters
        "ruff==${RUFF_VERSION}" \
        "yamllint==${YAMLLINT_VERSION}" \
        # Script dependencies (for mr_commit_linter)
        colorama \
        requests \
        # Testing dependencies
        pytest \
        pytest-mock \
    # Install Node.js linters
    && npm install -g "renovate@${RENOVATE_VERSION}"

# Copy shared linter configurations, scripts, and Makefile
# COPY automatically creates directories with ownership set via --chown
COPY --chown=1001:0 config/ /home/linter/.config/
COPY --chown=1001:0 scripts/ /home/linter/.scripts/
COPY --chown=1001:0 Makefile /home/linter/Makefile

# Set up directories and permissions for OpenShift compatibility
# OpenShift runs with arbitrary UIDs in GID 0 (root group), so g=u allows write access
RUN mkdir -p /workspace && \
    chown -R 1001:0 /workspace /home/linter && \
    chmod -R g=u /workspace /home/linter

# Use numeric UID for better compatibility
USER 1001
ENV HOME=/home/linter
WORKDIR /workspace

# Set PATH to include local bin directories
ENV PATH="/home/linter/.local/bin:${PATH}"

# Default command
CMD ["/bin/bash"]
