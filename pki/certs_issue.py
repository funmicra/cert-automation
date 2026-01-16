import json
import re
from pathlib import Path
import subprocess

# Configuration
EXPORT_DIR = Path("./certs")
EXPORT_DIR.mkdir(exist_ok=True)
JSON_FILE = Path("vault_san.json")
ALT_NAMES_FILE = Path("pki/alt_names.txt")  # File with SANs, one per line

# Read alt_names from file
if not ALT_NAMES_FILE.exists():
    raise FileNotFoundError(f"{ALT_NAMES_FILE} does not exist")

with ALT_NAMES_FILE.open() as f:
    alt_names_list = [line.strip() for line in f if line.strip()]
alt_names_str = ",".join(alt_names_list)

# Vault command
vault_command = [
    "vault", "write", "-format=json", "pki-int/issue/syndicate",
    "common_name=syndicate",
    f"alt_names={alt_names_str}",
    "ttl=48h",
    "format=pem_bundle"
]

# Run Vault command and save output
with JSON_FILE.open("w") as f:
    subprocess.run(vault_command, stdout=f, check=True)

# Load JSON
with JSON_FILE.open() as f:
    raw = json.load(f)

data = raw.get("data", {})

leaf_pem = data.get("certificate")
ca_chain = data.get("ca_chain", [])
issuing_ca = data.get("issuing_ca")

if not leaf_pem:
    raise ValueError("Leaf certificate (or private key) missing in JSON!")

# Extract private key and certificate
private_key_match = re.search(
    r"(-----BEGIN .*PRIVATE KEY-----.*?-----END .*PRIVATE KEY-----)", leaf_pem, re.DOTALL
)
cert_match = re.search(
    r"(-----BEGIN CERTIFICATE-----.*?-----END CERTIFICATE-----)", leaf_pem, re.DOTALL
)

if not private_key_match or not cert_match:
    raise ValueError("Cannot extract private key or certificate from JSON!")

private_key = private_key_match.group(1).strip()
leaf_cert = cert_match.group(1).strip()

def clean_pem(pem: str) -> str:
    return "\n".join(line.strip() for line in pem.splitlines() if line.strip()) + "\n"

private_key = clean_pem(private_key)
leaf_cert = clean_pem(leaf_cert)
ca_chain = [clean_pem(c) for c in ca_chain]

# Write files
key_file = EXPORT_DIR / "syndicate.key"
key_file.write_text(private_key)
key_file.chmod(0o600)

(EXPORT_DIR / "syndicate.pem").write_text(leaf_cert)

intermediates_only = ca_chain[:-1] if len(ca_chain) > 1 else []
fullchain = "\n".join([leaf_cert] + intermediates_only)
(EXPORT_DIR / "fullchain.pem").write_text(fullchain)

if issuing_ca:
    (EXPORT_DIR / "intermediate.pem").write_text(clean_pem(issuing_ca))

print(f"Certificates and key exported successfully to {EXPORT_DIR.resolve()}")
