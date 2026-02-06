# Using ubi10/nodejs-22 as base image because Renovate requires Node.js 22
ARG BASE_IMAGE=registry.access.redhat.com/ubi10/nodejs-22:10.0-1762806356
FROM ${BASE_IMAGE}

ARG RUFF_VERSION=0.14.2
ARG YAMLLINT_VERSION=1.38.0
ARG RENOVATE_VERSION=43.4.0

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

# Set up directories for OpenShift compatibility (UID 1001 already exists in base image)
# OpenShift runs with arbitrary UIDs in GID 0 (root group)
RUN mkdir -p /workspace /home/linter/.config/ /home/linter/.scripts/ && \
    chown -R 1001:0 /workspace /home/linter && chmod -R g=u /workspace /home/linter

# Copy shared linter configurations and scripts
# Place in user's home directory so they're accessible and follow XDG conventions
# Set ownership to root group (GID 0) for OpenShift arbitrary UID support
COPY --chown=1001:0 config/ /home/linter/.config/
COPY --chown=1001:0 scripts/ /home/linter/.scripts/
RUN chmod -R g=u /home/linter/.config/ /home/linter/.scripts/

# Use numeric UID for better compatibility
USER 1001
ENV HOME=/home/linter
WORKDIR /workspace

# Set PATH to include local bin directories
ENV PATH="/home/linter/.local/bin:${PATH}"

# Default command
CMD ["/bin/bash"]
