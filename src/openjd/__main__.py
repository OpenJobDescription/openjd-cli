# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

import sys
import traceback

from .cli._create_argparser import create_argparser

__all__ = ("main",)


def main() -> None:
    parser = create_argparser()

    args = parser.parse_args(sys.argv[1:])
    try:
        # Raises:
        #  SystemExit - on failure
        args.func(args)
    except Exception as exc:
        print(f"ERROR: {str(exc)}", file=sys.stderr)
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
