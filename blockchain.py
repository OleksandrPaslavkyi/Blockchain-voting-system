# blockchain.py
import hashlib
import json
import os
from time import time
from crypto_utils import hash_block_for_signing, verify_pem

FIXED_GENESIS_BLOCK = {
    "index": 0,
    "timestamp": 1763476947.0,
    "transactions": ["Genesis Block"],
    "previous_hash": "0",
    "proposer": None,
    "proposer_sig": None,
    "signatures": [],
    "hash": "6d0c9826f4079236c2a09067d2d2efccc32de9060075ed2df4fdb4b6a307e7a7"
}

class Block:
    def __init__(self, index, transactions, previous_hash, timestamp=None, hash=None, proposer=None, proposer_sig=None, signatures=None):
        self.index = index
        self.timestamp = timestamp or time()
        self.transactions = transactions
        self.previous_hash = previous_hash
        self.proposer = proposer
        self.proposer_sig = proposer_sig
        self.signatures = signatures or []
        self.hash = hash or self.calculate_hash()

    def calculate_hash(self):
        block_string = json.dumps({
            "index": self.index,
            "timestamp": self.timestamp,
            "transactions": self.transactions,
            "previous_hash": self.previous_hash,
            "proposer": self.proposer
        }, sort_keys=True).encode()
        return hashlib.sha256(block_string).hexdigest()

    def to_dict(self):
        return {
            "index": self.index,
            "timestamp": self.timestamp,
            "transactions": self.transactions,
            "previous_hash": self.previous_hash,
            "proposer": self.proposer,
            "proposer_sig": self.proposer_sig,
            "signatures": self.signatures,
            "hash": self.hash
        }

class Blockchain:
    def __init__(self, file_path="blockchain_data.json", validators_config="validators.json", max_tx_per_block=3):
        self.file_path = file_path
        self.chain = []
        self.current_transactions = []
        self.max_tx_per_block = max_tx_per_block
        self.validators_config = validators_config
        self.validators = []
        self.load_validators()
        self.load_chain()

    def load_validators(self):
        if os.path.exists(self.validators_config):
            with open(self.validators_config, "r") as f:
                cfg = json.load(f)
                self.validators = cfg.get("validators", [])
        else:
            self.validators = []

    def create_genesis_block(self):
        """Create the fixed genesis block"""
        genesis_block = Block(
            FIXED_GENESIS_BLOCK['index'],
            FIXED_GENESIS_BLOCK['transactions'],
            FIXED_GENESIS_BLOCK['previous_hash'],
            FIXED_GENESIS_BLOCK['timestamp'],
            FIXED_GENESIS_BLOCK['hash'],
            FIXED_GENESIS_BLOCK['proposer'],
            FIXED_GENESIS_BLOCK['proposer_sig'],
            FIXED_GENESIS_BLOCK['signatures']
        )
        self.chain.append(genesis_block)
        self.save_chain()

    def append_committed_block(self, block_dict):
        """
        Validate and append a committed block (with proposer_sig and signatures)
        Returns (True, msg) or (False, msg)
        """
        if self.chain and block_dict['previous_hash'] != self.chain[-1].hash:
            return False, "previous_hash mismatch"

        proposer = block_dict.get('proposer')
        proposer_pub = self._get_validator_pubkey(proposer)
        if not proposer_pub:
            return False, "unknown proposer"

        h = hash_block_for_signing(block_dict)
        if not verify_pem(proposer_pub, h, block_dict.get('proposer_sig', '')):
            return False, "invalid proposer signature"

        sigs = block_dict.get('signatures', [])
        valid_sigs = set()
        for entry in sigs:
            vid = entry.get('validator')
            sig = entry.get('sig')
            vpub = self._get_validator_pubkey(vid)
            if vpub and verify_pem(vpub, h, sig):
                valid_sigs.add(vid)

        needed = 1
        if len(valid_sigs) < needed:
            return False, f"not enough valid signatures ({len(valid_sigs)}/{needed})"

        # Ensure hash is included
        block_hash = block_dict.get('hash')
        if not block_hash:
            block_hash = Block(
                block_dict['index'],
                block_dict['transactions'],
                block_dict['previous_hash'],
                block_dict['timestamp'],
                None,
                block_dict.get('proposer')
            ).calculate_hash()

        block_obj = Block(
            block_dict['index'],
            block_dict['transactions'],
            block_dict['previous_hash'],
            block_dict['timestamp'],
            block_hash,
            block_dict.get('proposer'),
            block_dict.get('proposer_sig'),
            block_dict.get('signatures')
        )
        self.chain.append(block_obj)

        # Remove transactions from mempool
        for tx in block_obj.transactions:
            if tx in self.current_transactions:
                self.current_transactions.remove(tx)

        self.save_chain()
        return True, "appended"

    def to_dict(self):
        return [b.to_dict() for b in self.chain]

    def save_chain(self):
        with open(self.file_path, "w") as f:
            json.dump(self.to_dict(), f, indent=4)

    def load_chain(self):
        if os.path.exists(self.file_path):
            with open(self.file_path, "r") as f:
                data = json.load(f)
                if data:
                    self.chain = [
                        Block(
                            block["index"],
                            block["transactions"],
                            block["previous_hash"],
                            block["timestamp"],
                            block.get("hash"),
                            block.get("proposer"),
                            block.get("proposer_sig"),
                            block.get("signatures", [])
                        ) for block in data
                    ]
                    return
        # file missing or empty → create fixed genesis block
        self.create_genesis_block()

    def count_votes(self):
        yes_count = 0
        no_count = 0
        for block in self.chain:
            for tx in block.transactions:
                if isinstance(tx, str) and tx.startswith("Vote: YES"):
                    yes_count += 1
                elif isinstance(tx, str) and tx.startswith("Vote: NO"):
                    no_count += 1
        for tx in self.current_transactions:
            if isinstance(tx, str) and tx.startswith("Vote: YES"):
                yes_count += 1
            elif isinstance(tx, str) and tx.startswith("Vote: NO"):
                no_count += 1
        return {"YES": yes_count, "NO": no_count}

    def is_chain_valid(self):
        for i in range(1, len(self.chain)):
            current = self.chain[i]
            previous = self.chain[i - 1]
            if current.hash != current.calculate_hash():
                return False, f"Block {current.index} has invalid hash!"
            if current.previous_hash != previous.hash:
                return False, f"Block {current.index} has invalid previous hash!"
        return True, "Blockchain is valid!"

    def _get_validator_pubkey(self, validator_id):
        for v in self.validators:
            if v.get('id') == validator_id:
                if 'pubkey' in v:
                    return v['pubkey']
                elif 'pubkey_file' in v and os.path.exists(v['pubkey_file']):
                    with open(v['pubkey_file'], 'r') as f:
                        return f.read()
        return None
