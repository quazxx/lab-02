"""Точка входа программы."""

from streamstats.cli import build_parser, execute


def main(argv: list[str] | None = None) -> None:
    """Разбирает аргументы и запускает команду analyze."""
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command != "analyze":
        parser.print_help()
        return
    execute(args)
