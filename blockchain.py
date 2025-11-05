import hashlib
import json
import os
from time import time


class Block:
    def __init__(self, index, transactions, previous_hash, timestamp=None, hash=None):
        self.index = index
        self.timestamp = timestamp or time()
        self.transactions = transactions
        self.previous_hash = previous_hash
        self.hash = hash or self.calculate_hash()

    def calculate_hash(self):
        block_string = json.dumps({
            "index": self.index,
            "timestamp": self.timestamp,
            "transactions": self.transactions,
            "previous_hash": self.previous_hash
        }, sort_keys=True).encode()
        return hashlib.sha256(block_string).hexdigest()


class Blockchain:
    def __init__(self, file_path="blockchain_data.json", max_tx_per_block=3):
        self.file_path = file_path
        self.chain = []
        self.current_transactions = []
        self.max_tx_per_block = max_tx_per_block
        self.load_chain()

    def create_genesis_block(self):
        genesis_block = Block(0, ["Genesis Block"], "0")
        self.chain.append(genesis_block)
        self.save_chain()

    def add_transaction(self, transaction):
        self.current_transactions.append(transaction)

        if len(self.current_transactions) >= self.max_tx_per_block:
            self.add_block()

        self.save_chain()

    def add_block(self):
        if not self.current_transactions:
            return

        previous_hash = self.chain[-1].hash
        new_block = Block(len(self.chain), self.current_transactions, previous_hash)
        self.current_transactions = []
        self.chain.append(new_block)
        self.save_chain()

    def to_dict(self):
        return [vars(block) for block in self.chain]

    def save_chain(self):
        with open(self.file_path, "w") as f:
            json.dump(self.to_dict(), f, indent=4)

    def load_chain(self):
        if os.path.exists(self.file_path):
            with open(self.file_path, "r") as f:
                data = json.load(f)
                self.chain = [
                    Block(
                        block["index"],
                        block["transactions"],
                        block["previous_hash"],
                        block["timestamp"],
                        block["hash"]
                    ) for block in data
                ]
        else:
            self.create_genesis_block()

    def count_votes(self):
        yes_count = 0
        no_count = 0
        for block in self.chain:
            for tx in block.transactions:
                if tx.startswith("Vote: YES"):
                    yes_count += 1
                elif tx.startswith("Vote: NO"):
                    no_count += 1

        for tx in self.current_transactions:
            if tx.startswith("Vote: YES"):
                yes_count += 1
            elif tx.startswith("Vote: NO"):
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


