# app.py
import argparse
import threading
import time
import requests
import json
import os
from flask import Flask, render_template, request, jsonify, redirect
from blockchain import Blockchain
from crypto_utils import sign_pem, hash_block_for_signing, verify_pem

app = Flask(__name__)

# ---------- CLI args ----------
parser = argparse.ArgumentParser()
parser.add_argument("--port", type=int, required=True)
parser.add_argument("--id", required=True)
parser.add_argument("--sk", required=True)
parser.add_argument("--validators", default="validators.json")
parser.add_argument("--chain", default=None)  # optional override for chain file
parser.add_argument("--max-tx", type=int, default=3)
args = parser.parse_args()

PORT = args.port
NODE_ID = args.id
SK_FILE = args.sk
VALIDATORS_FILE = args.validators
MAX_TX = args.max_tx

if not os.path.exists(SK_FILE):
    raise SystemExit(f"Private key file not found: {SK_FILE}")

SK_PEM = open(SK_FILE, "r").read()
CHAIN_FILE = args.chain or f"chain_{NODE_ID}.json"

# ---------- Initialize blockchain ----------
blockchain = Blockchain(file_path=CHAIN_FILE, validators_config=VALIDATORS_FILE, max_tx_per_block=MAX_TX)
validators = blockchain.validators
NUM_VALIDATORS = max(1, len(validators))
THRESHOLD = (NUM_VALIDATORS // 2) + 1

# in-memory mempool
mempool = []

# ---------- Flask routes (frontend) ----------
@app.route('/')
def index():
    chain_data = blockchain.to_dict()
    vote_counts = blockchain.count_votes()
    return render_template('index.html', chain=chain_data, vote_counts=vote_counts)

@app.route('/vote', methods=['POST'])
def vote_form():
    vote_value = request.form.get('vote') or (request.json or {}).get('vote')
    if vote_value and vote_value.upper() in ("YES", "NO"):
        tx = f"Vote: {vote_value.upper()}"
        mempool.append(tx)
        blockchain.save_chain()  # just save mempool/chain
    return redirect('/')

@app.route('/tx', methods=['POST'])
def tx():
    data = request.get_json() or {}
    vote = data.get('vote')
    if not vote or vote.upper() not in ("YES","NO"):
        return jsonify({"error":"invalid vote"}), 400
    tx = f"Vote: {vote.upper()}"
    mempool.append(tx)
    blockchain.save_chain()
    return jsonify({"status":"ok", "mempool": len(mempool)}), 201

@app.route('/chain', methods=['GET'])
def get_chain():
    return jsonify(blockchain.to_dict())

# Receive propose: validator signs block proposal
@app.route('/propose', methods=['POST'])
def receive_proposal():
    payload = request.get_json() or {}
    block = payload.get("block")
    proposer_sig = payload.get("proposer_sig")
    if not block or not proposer_sig:
        return jsonify({"error":"missing data"}), 400
    proposer_id = block.get("proposer")
    proposer_pub = blockchain._get_validator_pubkey(proposer_id)
    if not proposer_pub:
        return jsonify({"error":"unknown proposer"}), 400
    h = hash_block_for_signing(block)
    if not verify_pem(proposer_pub, h, proposer_sig):
        return jsonify({"error":"invalid proposer signature"}), 400
    my_sig = sign_pem(SK_PEM, h)
    return jsonify({"validator": NODE_ID, "sig": my_sig}), 200

# Receive commit: append committed block
@app.route('/commit', methods=['POST'])
def receive_commit():
    payload = request.get_json() or {}
    block = payload.get("block")
    if not block:
        return jsonify({"error":"missing block"}), 400
    ok, msg = blockchain.append_committed_block(block)
    if not ok:
        return jsonify({"error": msg}), 400
    for tx in block.get("transactions", []):
        if tx in mempool:
            mempool.remove(tx)
    return jsonify({"status":"committed"}), 200

@app.route('/mempool')
def view_mempool():
    return jsonify({"mempool": mempool})

# ---------- proposer loop ----------
def proposer_loop():
    global validators, NUM_VALIDATORS, THRESHOLD
    while True:
        time.sleep(0.5)
        validators = blockchain.validators
        NUM_VALIDATORS = max(1, len(validators))
        THRESHOLD = max(1, (NUM_VALIDATORS // 2) + 1)

        if len(mempool) < MAX_TX:
            continue

        # round-robin proposer
        height = len(blockchain.chain)
        proposer_index = height % NUM_VALIDATORS
        proposer_id = validators[proposer_index]['id'] if NUM_VALIDATORS > 0 else None
        if proposer_id != NODE_ID:
            continue

        # build block candidate
        block_candidate = {
            "index": height,
            "timestamp": time.time(),
            "transactions": mempool[:MAX_TX],
            "previous_hash": blockchain.chain[-1].hash,
            "proposer": NODE_ID
        }
        h = hash_block_for_signing(block_candidate)
        proposer_sig = sign_pem(SK_PEM, h)

        # broadcast propose to validators
        sigs = []
        for v in validators:
            try:
                r = requests.post(f"{v['host']}/propose", json={"block": block_candidate, "proposer_sig": proposer_sig}, timeout=3)
                if r.status_code == 200:
                    resp = r.json()
                    sigs.append(resp)
            except Exception:
                pass

        # include proposer signature if missing
        if not any(s.get('validator') == NODE_ID for s in sigs):
            sigs.append({"validator": NODE_ID, "sig": proposer_sig})

        # dedupe signatures
        unique = {}
        for s in sigs:
            vid = s.get('validator')
            sig = s.get('sig')
            if vid and sig:
                unique[vid] = sig

        # commit if threshold reached
        if len(unique) >= THRESHOLD:
            block_candidate['proposer_sig'] = proposer_sig
            block_candidate['signatures'] = [{"validator": k, "sig": v} for k, v in unique.items()]

            # broadcast commit
            for v in validators:
                try:
                    requests.post(f"{v['host']}/commit", json={"block": block_candidate}, timeout=3)
                except Exception:
                    pass

            # locally append
            blockchain.append_committed_block(block_candidate)

            # remove transactions from mempool
            for tx in block_candidate['transactions']:
                if tx in mempool:
                    mempool.remove(tx)

if __name__ == "__main__":
    t = threading.Thread(target=proposer_loop, daemon=True)
    t.start()
    app.run(host="0.0.0.0", port=PORT, debug=False)
