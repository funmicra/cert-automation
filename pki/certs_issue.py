import json
import re
import subprocess
from pathlib import Path

# =========================
# Configuration
# =========================

EXPORT_DIR = Path("pki/certs")
EXPORT_DIR.mkdir(parents=True, exist_ok=True)

JSON_FILE = Path("pki/vault_san.json")
ALT_NAMES_FILE = Path("pki/alt_names.txt")  # one SAN per line

# =========================
# Helpers
# =========================

def clean_pem(pem: str) -> str:
    """Normalize PEM formatting."""
    return "\n".join(line.strip() for line in pem.splitlines() if line.strip()) + "\n"

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

# Run Vault command and save JSON response
subprocess.run(vault_command, stdout=JSON_FILE.open("w"), check=True)

# =========================
# Parse Vault response
# =========================

with JSON_FILE.open() as f:
    raw = json.load(f)

data = raw.get("data", {})

leaf_bundle = data.get("certificate")
issuing_ca = data.get("issuing_ca")
ca_chain = data.get("ca_chain", [])

if not leaf_bundle or not issuing_ca or not ca_chain:
    raise ValueError("Vault response missing required certificates")

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
root_ca = clean_pem(ca_chain[0])  # first element in ca_chain is root

# =========================
# Write files
# =========================
# Clean PEMs
ca_chain = [clean_pem(c) for c in ca_chain]

# Assign intermediate(s) and root properly
if len(ca_chain) == 1:
    root_ca = ca_chain[0]
    intermediates = ""
elif len(ca_chain) >= 2:
    root_ca = ca_chain[-1]                  # last is root
    intermediates = "\n".join(ca_chain[:-1])  # all others are intermediates
else:
    raise RuntimeError("No CA certificates returned from Vault")

# Write files
key_file = EXPORT_DIR / "syndicate.key"
key_file.write_text(private_key)
key_file.chmod(0o600)

(EXPORT_DIR / "syndicate.pem").write_text(leaf_cert)
(EXPORT_DIR / "intermediate.pem").write_text(intermediates)
(EXPORT_DIR / "fullchain.pem").write_text(leaf_cert + "\n" + intermediates)
(EXPORT_DIR / "root-ca.pem").write_text(root_ca)

# =========================
# Validate chain
# =========================

cmd = [
    "openssl", "verify",
    "-CAfile", str(EXPORT_DIR / "root-ca.pem"),
    "-untrusted", str(EXPORT_DIR / "intermediate.pem"),
    str(EXPORT_DIR / "syndicate.pem")
]

result = subprocess.run(cmd, capture_output=True, text=True)
if result.returncode != 0:
    raise RuntimeError(f"Certificate chain validation failed:\n{result.stderr}")

print("Certificate chain validation passed ✅")
