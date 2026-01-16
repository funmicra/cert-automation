import json
import re
from pathlib import Path
import subprocess

# Configuration
EXPORT_DIR = Path("./certs")
EXPORT_DIR.mkdir(exist_ok=True)

JSON_FILE = Path("vault_san.json")
ALT_NAMES_FILE = Path("pki/alt_names.txt")

# Read SANs
if not ALT_NAMES_FILE.exists():
    raise FileNotFoundError(f"{ALT_NAMES_FILE} does not exist")

with ALT_NAMES_FILE.open() as f:
    alt_names = [line.strip() for line in f if line.strip()]

alt_names_str = ",".join(alt_names)

# Vault command
vault_command = [
    "vault", "write", "-format=json",
    "pki-int/issue/syndicate",
    "common_name=syndicate",
    f"alt_names={alt_names_str}",
    "ttl=48h",
    "format=pem_bundle"
]

# Run Vault command
with JSON_FILE.open("w") as f:
    subprocess.run(vault_command, stdout=f, check=True)

# Load Vault response
with JSON_FILE.open() as f:
    raw = json.load(f)

data = raw.get("data", {})

leaf_bundle = data.get("certificate")
issuing_ca = data.get("issuing_ca")
ca_chain = data.get("ca_chain", [])

if not leaf_bundle or not issuing_ca:
    raise ValueError("Vault response missing certificate or issuing_ca")

# Extract private key + leaf cert
private_key_match = re.search(
    r"(-----BEGIN .*PRIVATE KEY-----.*?-----END .*PRIVATE KEY-----)",
    leaf_bundle,
    re.DOTALL
)
leaf_cert_match = re.search(
    r"(-----BEGIN CERTIFICATE-----.*?-----END CERTIFICATE-----)",
    leaf_bundle,
    re.DOTALL
)

if not private_key_match or not leaf_cert_match:
    raise ValueError("Failed to extract private key or leaf certificate")

def clean_pem(pem: str) -> str:
    return "\n".join(line.strip() for line in pem.splitlines() if line.strip()) + "\n"

private_key = clean_pem(private_key_match.group(1))
leaf_cert = clean_pem(leaf_cert_match.group(1))
issuing_ca = clean_pem(issuing_ca)
ca_chain = [clean_pem(c) for c in ca_chain]

# Write key and leaf
(EXPORT_DIR / "syndicate.key").write_text(private_key)
(EXPORT_DIR / "syndicate.key").chmod(0o600)

(EXPORT_DIR / "syndicate.pem").write_text(leaf_cert)

# Build FULLCHAIN CORRECTLY
# leaf + issuing CA + any additional intermediates (exclude root)
fullchain_parts = [leaf_cert, issuing_ca]

# ca_chain may contain issuing_ca again → avoid duplication
for cert in ca_chain:
    if cert not in fullchain_parts:
        fullchain_parts.append(cert)

# Drop root CA if present (last cert in chain)
fullchain_parts = fullchain_parts[:-1]

fullchain_pem = "\n".join(fullchain_parts)
(EXPORT_DIR / "fullchain.pem").write_text(fullchain_pem)

# Export root CA separately (optional but recommended)
if ca_chain:
    root_ca = ca_chain[-1]
    (EXPORT_DIR / "root-ca.pem").write_text(root_ca)

print(f"Certificates exported to {EXPORT_DIR.resolve()}")
