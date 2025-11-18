# generate_keys.py
from crypto_utils import generate_keypair
import sys, os

if len(sys.argv) < 2:
    print("Usage: python generate_keys.py <node_id>")
    sys.exit(1)

node = sys.argv[1]
sk, vk = generate_keypair()
sk_file = f"{node}_sk.pem"
vk_file = f"{node}_vk.pem"
open(sk_file, "w").write(sk)
open(vk_file, "w").write(vk)
print("Generated keys:", sk_file, vk_file)
print("Don't share the _sk.pem file!")
