#!/usr/bin/env python3
import argparse
import secrets

from backend.common.pass_auth import hash_password

def main() -> None:
    parser = argparse.ArgumentParser(description="Generate salt and password hash")
    parser.add_argument("password", help="Plain text password")
    parser.add_argument("--salt", default=None, help="Optional salt")
    args = parser.parse_args()

    salt = args.salt or secrets.token_hex(8)
    password_hash = hash_password(args.password, salt)

    print(f"salt={salt}")
    print(f"password_hash={password_hash}")


if __name__ == "__main__":
    main()
