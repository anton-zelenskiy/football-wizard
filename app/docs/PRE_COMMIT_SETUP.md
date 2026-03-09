# Pre-commit Setup Guide

This project uses pre-commit hooks with ruff for automatic code formatting and linting.

## Quick Setup

Run the setup script to install and configure pre-commit:

```bash
./setup-pre-commit.sh
```

## Manual Setup

If you prefer to set up manually:

1. Install dependencies:
   ```bash
   pip install pre-commit ruff
   ```

2. Install the pre-commit hooks:
   ```bash
   pre-commit install
   ```

3. Test the setup:
   ```bash
   pre-commit run --all-files
   ```

## What's Included

The pre-commit configuration includes:

- **Ruff linter** - Fast Python linter with auto-fix capabilities
- **Ruff formatter** - Code formatting
- **Import sorting** - Automatic import organization and sorting
- **Basic hooks** - Trailing whitespace, end-of-file, YAML validation, etc.

## Configuration

- **Ruff settings**: Configured in `pyproject.toml`
- **Pre-commit hooks**: Configured in `.pre-commit-config.yaml`

## Import Sorting

The pre-commit hooks include automatic import sorting with the following features:

- **Automatic sorting** of import statements
- **Grouping** imports by type (standard library, third-party, local)
- **Consistent formatting** with proper spacing
- **Removal** of unused imports
- **Organization** of import statements within each group

Import order:
1. Standard library imports
2. Third-party imports
3. Local application imports (from `app` package)

## Usage

### Automatic (Recommended)
Hooks run automatically on `git commit`. If issues are found, they'll be fixed automatically when possible.

### Manual
```bash
# Run on all files
pre-commit run --all-files

# Run on staged files only
pre-commit run

# Run on specific files
pre-commit run --files app/main.py
```

## Skipping Hooks (Not Recommended)

If you need to skip hooks for a specific commit:

```bash
git commit --no-verify -m "your message"
```

## Updating Hooks

To update to the latest versions:

```bash
pre-commit autoupdate
pre-commit run --all-files
```

## Troubleshooting

### Common Issues

1. **Hooks fail on commit**: Check the output for specific errors and fix them
2. **Slow performance**: Ruff is very fast, but you can exclude large directories in `pyproject.toml`
3. **Import errors**: Make sure all dependencies are installed in your environment

### Getting Help

- Check the [pre-commit documentation](https://pre-commit.com/)
- Check the [ruff documentation](https://docs.astral.sh/ruff/)
- Run `pre-commit run --all-files --verbose` for detailed output
