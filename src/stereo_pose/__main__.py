"""``python -m stereo_pose`` entry point.

Subcommands:
  doctor  offline environment health check
  run     launch the live-camera pipeline (requires cameras + model weights)
"""

from __future__ import annotations

import sys


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)

    if not argv or argv[0] in ("-h", "--help"):
        print("usage: python -m stereo_pose <doctor|run> [options]")
        return 0

    cmd = argv[0]
    rest = argv[1:]

    if cmd == "doctor":
        from stereo_pose.diagnostics.doctor import main as doctor_main

        return doctor_main(rest)
    if cmd == "run":
        from stereo_pose.app.runner import main as run_main

        # Patch argv for the sub-command parser.
        old = sys.argv
        sys.argv = ["stereo_pose run"] + rest
        try:
            run_main()
        finally:
            sys.argv = old
        return 0

    print(f"unknown command: {cmd}")
    print("usage: python -m stereo_pose <doctor|run> [options]")
    return 2


if __name__ == "__main__":
    sys.exit(main())