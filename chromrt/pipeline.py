"""Run phase 2 locally: prepare → validate frozen splits → development baseline."""
from chromrt import prepare, splits, baseline


def main():
    prepare.main()
    splits.main()
    baseline.main()


if __name__ == '__main__':
    main()
