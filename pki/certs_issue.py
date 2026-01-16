import json
import re
import subprocess
from pathlib import Path

# =========================
# Configuration
# =========================

EXPORT_DIR = Path("./certs")
EXPORT_DIR.mkdir(parents=True, exist_ok=True)

JSON_FILE = Path("vault_san.json")
ALT_NAMES_FILE = Path("pki/alt_names.txt")  # one SAN per line

# =========================
# Helpers
# =========================

def clean_pem(pem: str) -> str:
    return "\n".join(
        line.strip() for line in pem.splitlines() if line.strip()
    ) + "\n"

def extract_block(pattern: str, text: str, name: str) -> str:
    match = re.search(pattern, text, re.DOTALL)
    if not match:
        raise ValueError(f"Cannot extract {name}")
    return clean_pem(match.group(1))

# =========================
# Read SANs
# =========================

if not ALT_NAMES_FILE.exists():
    raise FileNotFoundError(f"{ALT_NAMES_FILE} does not exist")

with ALT_NAMES_FILE.open() as f:
    alt_names = [line.strip() for line in f if line.strip()]

if not alt_names:
    raise ValueError("ALT names file is empty")

alt_names_str = ",".join(alt_names)

# =========================
# Issue cert from Vault
# =========================

vault_command = [
    "vault", "write", "-format=json",
    "pki-int/issue/syndicate",
    "common_name=syndicate",
    f"alt_names={alt_names_str}",
    "ttl=48h",
    "format=pem_bundle",
]

with JSON_FILE.open("w") as f:
    subprocess.run(vault_command, stdout=f, check=True)

# =========================
# Parse Vault response
# =========================

with JSON_FILE.open() as f:
    raw = json.load(f)

data = raw.get("data", {})

leaf_bundle = data.get("certificate")
issuing_ca = data.get("issuing_ca")

if not leaf_bundle:
    raise ValueError("Vault response missing certificate bundle")

if not issuing_ca:
    raise ValueError("Vault response missing issuing_ca (intermediate)")

# =========================
# Extract leaf + key
# =========================

private_key = extract_block(
    r"(-----BEGIN .*PRIVATE KEY-----.*?-----END .*PRIVATE KEY-----)",
    leaf_bundle,
    "private key",
)

leaf_cert = extract_block(
    r"(-----BEGIN CERTIFICATE-----.*?-----END CERTIFICATE-----)",
    leaf_bundle,
    "leaf certificate",
)

issuing_ca = clean_pem(issuing_ca)

# =========================
# Write files
# =========================

key_file = EXPORT_DIR / "syndicate.key"
key_file.write_text(private_key)
key_file.chmod(0o600)

(EXPORT_DIR / "syndicate.pem").write_text(leaf_cert)

# 🔒 FULLCHAIN RULE:
# leaf + issuing intermediate ONLY
fullchain = leaf_cert + issuing_ca
(EXPORT_DIR / "fullchain.pem").write_text(fullchain)

# Optional: keep intermediate explicit for debugging / audits
(EXPORT_DIR / "intermediate.pem").write_text(issuing_ca)

print("Certificates successfully issued:")
print(f" - {EXPORT_DIR / 'syndicate.key'}")
print(f" - {EXPORT_DIR / 'syndicate.pem'}")
print(f" - {EXPORT_DIR / 'fullchain.pem'}")
print(f" - {EXPORT_DIR / 'intermediate.pem'}")

