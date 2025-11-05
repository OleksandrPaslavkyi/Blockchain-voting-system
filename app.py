from flask import Flask, render_template, request, jsonify, redirect
from blockchain import Blockchain

app = Flask(__name__)
blockchain = Blockchain()

@app.route('/')
def index():
    chain_data = blockchain.to_dict()
    vote_counts = blockchain.count_votes()
    return render_template('index.html', chain=chain_data, vote_counts=vote_counts)


@app.route('/vote', methods=['POST'])
def vote():
    vote_value = request.form.get('vote')
    if vote_value:
        blockchain.add_transaction(f"Vote: {vote_value}")
    return redirect('/')


@app.route('/chain')
def get_chain():
    return jsonify(blockchain.to_dict())

@app.route('/blocks')
def view_blocks():
    chain_data = blockchain.to_dict()
    vote_counts = blockchain.count_votes()
    return render_template('blocks.html', chain=chain_data, vote_counts=vote_counts, validation_result=None)

@app.route('/blocks/validate', methods=['POST'])
def validate():
    valid, message = blockchain.is_chain_valid()
    chain_data = blockchain.to_dict()
    vote_counts = blockchain.count_votes()
    return render_template( 'blocks.html', chain=chain_data, vote_counts=vote_counts, validation_result=message)



if __name__ == '__main__':
    app.run(debug=True)

