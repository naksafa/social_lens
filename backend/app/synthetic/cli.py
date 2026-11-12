"""Write synthetic native-format exports to disk.

python -m app.synthetic.cli --business agency_uae --days 90 --seed 42 --out ../data/sample
"""

import argparse
from pathlib import Path

from app.core.enums import Platform
from app.services.demo_service import generate_files, get_business
from app.synthetic.profiles import DEMO_BUSINESSES


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate synthetic social media exports.")
    parser.add_argument("--business", default="agency_uae", choices=list(DEMO_BUSINESSES))
    parser.add_argument("--days", type=int, default=90, choices=[30, 60, 90, 180])
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--posts", type=int, default=None, help="Posts per platform (default: profile plan)")
    parser.add_argument("--platforms", nargs="*", choices=[p.value for p in Platform])
    parser.add_argument("--clean", action="store_true", help="Do not inject data-quality issues")
    parser.add_argument("--out", type=Path, default=Path("../data/synthetic"))
    args = parser.parse_args()

    args.out.mkdir(parents=True, exist_ok=True)
    platforms = [Platform(p) for p in args.platforms] if args.platforms else None
    for platform, name, content in generate_files(
        get_business(args.business), args.days, args.seed, platforms, args.posts, inject_issues=not args.clean
    ):
        path = args.out / name
        path.write_bytes(content)
        print(f"{platform.value:10} -> {path}")


if __name__ == "__main__":
    main()
