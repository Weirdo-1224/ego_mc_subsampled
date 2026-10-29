"""Default entry point only prechecks local videos; mining is not implemented."""

from task_mining.preflight import main

if __name__ == "__main__":
    raise SystemExit(main())
