"""Allows `python -m cvforge` as well as the `cvforge` console script."""

from .cli import main

if __name__ == "__main__":
    raise SystemExit(main())
