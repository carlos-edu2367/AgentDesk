import json
import sys


def main() -> None:
    payload = json.load(sys.stdin)
    message = str(payload.get("message", ""))
    print(json.dumps({"echo": message}))


if __name__ == "__main__":
    main()
