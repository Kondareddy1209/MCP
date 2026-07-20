from __future__ import annotations

import argparse
import json
from pathlib import Path


DEFAULT_OUTPUT = Path("vapid_keys.json")


def _generate_with_py_vapid() -> dict[str, str]:
    from py_vapid import Vapid02
    from cryptography.hazmat.primitives import serialization

    vapid = Vapid02()
    vapid.generate_keys()
    public_key = vapid.public_key.public_bytes(
        encoding=serialization.Encoding.X962,
        format=serialization.PublicFormat.UncompressedPoint,
    )
    private_key = vapid.private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    return {
        "public_key": public_key.decode("utf-8") if isinstance(public_key, bytes) else str(public_key),
        "private_key": private_key.decode("utf-8") if isinstance(private_key, bytes) else str(private_key),
        "subject": "mailto:admin@example.com",
    }


def _generate_fallback() -> dict[str, str]:
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ec

    private_key = ec.generate_private_key(ec.SECP256R1())
    public_key = private_key.public_key()
    return {
        "public_key": public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        ).decode("utf-8"),
        "private_key": private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        ).decode("utf-8"),
        "subject": "mailto:admin@example.com",
    }


def generate_keys(force: bool = False, output_path: Path = DEFAULT_OUTPUT) -> Path:
    if output_path.exists() and not force:
        raise FileExistsError(f"{output_path} already exists. Pass --force to overwrite it.")

    try:
        keys = _generate_with_py_vapid()
    except Exception:
        keys = _generate_fallback()

    output_path.write_text(json.dumps(keys, indent=2), encoding="utf-8")
    return output_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate Web Push VAPID keys for local notifications.")
    parser.add_argument("--force", action="store_true", help="Overwrite an existing vapid_keys.json file.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="Output path for the generated keys JSON.")
    args = parser.parse_args()

    output_path = Path(args.output)
    try:
        written_path = generate_keys(force=args.force, output_path=output_path)
    except FileExistsError as exc:
        print(str(exc))
        return 1

    print(f"Wrote VAPID keys to {written_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())