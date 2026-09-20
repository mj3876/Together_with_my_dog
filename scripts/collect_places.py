"""Reuse the existing paginated TourAPI collector, narrowed to Daejeon."""
import argparse
from Together_with_my_dog_cityselection.fetch_pet_tourapi import main as collect


def main():
    parser = argparse.ArgumentParser(description="대전 숙박·음식점 후보 수집. 동반 규정은 별도 확인해야 합니다.")
    parser.add_argument("--output", required=True)
    parser.add_argument("--key-file", default=".secrets/pet_tourapi.key")
    args = parser.parse_args()
    return collect(["fetch", "--area-codes", "3", "--content-type-ids", "32", "39",
                    "--key-file", args.key_file, "--output", args.output])


if __name__ == "__main__":
    raise SystemExit(main())
