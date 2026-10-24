from flask import Blueprint, current_app, flash, redirect, render_template, session

blockchain_controller = Blueprint("blockchain", __name__)


@blockchain_controller.route("/blockchain")
def blockchain_view():
    blockchain = current_app.extensions["blockchain"]
    total_txs = sum(len(block.transactions) for block in blockchain.chain)
    return render_template(
        "blockchain.html",
        blocks=blockchain.to_dict()["chain"],
        pending=blockchain.pending_transactions,
        total_txs=total_txs,
        valid=blockchain.is_chain_valid(),
    )


@blockchain_controller.route("/mine", methods=["GET", "POST"])
def mine_block():
    if not session.get("admin"):
        return redirect("/")
    blockchain = current_app.extensions["blockchain"]
    blockchain.mine_pending_transactions("admin")
    blockchain.save()
    return redirect("/blockchain")


@blockchain_controller.route("/verify_chain")
def verify_chain():
    blockchain = current_app.extensions["blockchain"]
    if blockchain.is_chain_valid():
        flash("Blockchain is valid! ✅")
    else:
        flash("Blockchain invalid! ⚠️")
    return redirect("/blockchain")
