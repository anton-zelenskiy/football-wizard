#!/bin/bash

# Setup script for pre-commit hooks with ruff
# This script installs pre-commit and sets up the hooks

set -e

echo "🔧 Setting up pre-commit hooks with ruff..."

# Check if we're in a git repository
if [ ! -d ".git" ]; then
    echo "❌ Error: Not in a git repository. Please run this from the project root."
    exit 1
fi

# Install pre-commit if not already installed
if ! command -v pre-commit &> /dev/null; then
    echo "📦 Installing pre-commit..."
    pip install pre-commit
else
    echo "✅ pre-commit already installed"
fi

# Install ruff if not already installed
if ! command -v ruff &> /dev/null; then
    echo "📦 Installing ruff..."
    pip install ruff
else
    echo "✅ ruff already installed"
fi

# Install the pre-commit hooks
echo "🔗 Installing pre-commit hooks..."
pre-commit install

# Run pre-commit on all files to test the setup
echo "🧪 Testing pre-commit setup..."
pre-commit run --all-files

echo "✅ Pre-commit setup complete!"
echo ""
echo "📋 Available commands:"
echo "  pre-commit run --all-files    # Run hooks on all files"
echo "  pre-commit run                 # Run hooks on staged files"
echo "  pre-commit run --files <file>  # Run hooks on specific files"
echo ""
echo "💡 The hooks will now run automatically on git commit!"
