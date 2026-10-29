"""Preserve the V0.1 default precheck; explicitly opt in to V0.2 mining."""

import sys

from task_mining.preflight import main as preflight_main

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "mine":
        from annotation_pipeline.scripts.mine import main
        raise SystemExit(main(sys.argv[2:]))
    raise SystemExit(preflight_main())
