from blockchain import Block, Blockchain


def make_chain(difficulty=2):
    chain = Blockchain.__new__(Blockchain)
    chain.difficulty = difficulty
    chain.pending_transactions = []
    genesis = Block(0, [], "2026-01-01 00:00:00", "0")
    genesis.mine_block(difficulty)
    chain.chain = [genesis]
    second = Block(
        1,
        [{"position": "President", "candidate": "Candidate A"}],
        "2026-01-01 00:01:00",
        genesis.hash,
    )
    second.mine_block(difficulty)
    chain.chain.append(second)
    return chain


def test_block_hash_is_deterministic_for_same_contents():
    first = Block(1, [{"candidate": "A"}], "time", "previous")
    second = Block(1, [{"candidate": "A"}], "time", "previous")

    assert first.hash == second.hash
    first.nonce += 1
    assert first.calculate_hash() != second.hash


def test_valid_chain_passes_hash_link_and_proof_checks():
    assert make_chain().is_chain_valid() is True


def test_tampered_transaction_is_detected():
    chain = make_chain()
    chain.chain[1].transactions[0]["candidate"] = "Tampered Candidate"

    assert chain.is_chain_valid() is False


def test_previous_hash_mismatch_is_detected_even_when_block_hash_is_valid():
    chain = make_chain()
    forged = Block(
        1,
        [{"position": "President", "candidate": "Candidate A"}],
        "2026-01-01 00:01:00",
        "wrong-previous-hash",
    )
    forged.mine_block(chain.difficulty)
    chain.chain[1] = forged

    assert forged.hash == forged.calculate_hash()
    assert forged.hash.startswith("0" * chain.difficulty)
    assert chain.is_chain_valid() is False


def test_insufficient_proof_of_work_is_detected():
    chain = make_chain(difficulty=1)
    chain.difficulty = 64

    assert chain.is_chain_valid() is False


def test_block_index_must_match_chain_position():
    chain = make_chain()
    wrong_index = Block(
        7,
        chain.chain[1].transactions,
        chain.chain[1].timestamp,
        chain.chain[0].hash,
    )
    wrong_index.mine_block(chain.difficulty)
    chain.chain[1] = wrong_index

    assert chain.is_chain_valid() is False


def test_new_transaction_adds_ballot_and_position_fields():
    chain = make_chain()

    transaction_index = chain.new_transaction("President", "Candidate A", "ballot-1")

    assert transaction_index == 0
    assert chain.pending_transactions[0]["ballot_id"] == "ballot-1"
    assert chain.pending_transactions[0]["position"] == "President"
    assert chain.pending_transactions[0]["candidate"] == "Candidate A"


def test_mining_pending_transactions_links_and_clears_pending():
    chain = make_chain()
    old_hash = chain.chain[-1].hash
    chain.new_transaction("Secretary", "Candidate B", "ballot-2")

    chain.mine_pending_transactions("test-miner")

    assert len(chain.chain) == 3
    assert chain.chain[-1].previous_hash == old_hash
    assert chain.pending_transactions == []
    assert chain.is_chain_valid() is True


def test_mining_without_pending_transactions_is_noop():
    chain = make_chain()
    original_length = len(chain.chain)

    chain.mine_pending_transactions()

    assert len(chain.chain) == original_length


def test_blockchain_save_and_load_use_temporary_path(tmp_path):
    chain = make_chain()
    path = tmp_path / "isolated-chain.json"
    chain.save(str(path))

    loaded = Blockchain.load(str(path))

    assert loaded.is_chain_valid() is True
    assert len(loaded.chain) == 2