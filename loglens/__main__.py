"""Allow ``python -m loglens`` to run the CLI."""

from loglens.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
