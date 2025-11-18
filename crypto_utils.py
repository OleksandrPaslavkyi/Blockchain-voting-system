# crypto_utils.py
from ecdsa import SigningKey, VerifyingKey, SECP256k1
import base64, json, hashlib

def generate_keypair():
    sk = SigningKey.generate(curve=SECP256k1)
    vk = sk.get_verifying_key()
    return sk.to_pem().decode(), vk.to_pem().decode()

def sign_pem(sk_pem: str, message: bytes) -> str:
    sk = SigningKey.from_pem(sk_pem.encode())
    return base64.b64encode(sk.sign(message)).decode()

def verify_pem(vk_pem: str, message: bytes, sig_b64: str) -> bool:
    try:
        vk = VerifyingKey.from_pem(vk_pem.encode())
        sig = base64.b64decode(sig_b64)
        return vk.verify(sig, message)
    except Exception:
        return False

def hash_block_for_signing(block_dict):
    # deterministic ordering — exclude proposer_sig and signatures
    to_sign = {
        "index": block_dict["index"],
        "timestamp": block_dict["timestamp"],
        "transactions": block_dict["transactions"],
        "previous_hash": block_dict["previous_hash"],
        "proposer": block_dict.get("proposer")
    }
    s = json.dumps(to_sign, sort_keys=True).encode()
    return hashlib.sha256(s).digest()
