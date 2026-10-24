import app as voting_app
from controllers import voting as voting_controller


POSITIONS = {
    "president": "President",
    "vice_president": "Vice President",
    "secretary": "Secretary",
    "treasury": "Treasury",
}


def all_nota_choices():
    return {field: "NOTA" for field in POSITIONS}


def test_voting_page_redirects_before_student_authentication(client):
    response = client.get("/vote")

    assert response.status_code == 302
    assert response.location.endswith("/")


def test_submit_vote_redirects_without_student_session(client):
    response = client.post("/submit_vote", data=all_nota_choices())

    assert response.status_code == 302
    assert response.location.endswith("/")


def test_authenticated_student_can_open_voting_page(signed_in_student):
    response = signed_in_student.get("/vote")

    assert response.status_code == 200
    assert b"Cast Your Vote" in response.data


def test_valid_vote_is_persisted_and_added_to_blockchain(signed_in_student, system):
    response = signed_in_student.post("/submit_vote", data=all_nota_choices())

    assert response.status_code == 200
    assert system.ballots["A101"] == {
        "President": "NOTA",
        "Vice President": "NOTA",
        "Secretary": "NOTA",
        "Treasury": "NOTA",
    }
    assert len(system.blockchain.pending_transactions) == 4
    assert system.blockchain.saved == 1
    assert b"Vote cast successfully" in response.data
    assert b"Voting is Closed" not in response.data


def test_success_response_uses_current_admin_setting(signed_in_student, system, monkeypatch):
    setting_reads = iter(("true", "false"))
    monkeypatch.setattr(voting_controller, "get_setting", lambda key: next(setting_reads))

    response = signed_in_student.post("/submit_vote", data=all_nota_choices())

    assert response.status_code == 200
    assert b"Voting is Closed" in response.data
    assert b"Vote cast successfully" not in response.data


def test_missing_candidate_choices_are_rejected(signed_in_student, system):
    response = signed_in_student.post("/submit_vote", data={})

    assert response.status_code == 200
    assert b"select a valid candidate for every position" in response.data
    assert system.ballots == {}


def test_invalid_candidate_is_rejected(signed_in_student, system):
    choices = all_nota_choices()
    choices["president"] = "Not a candidate"

    response = signed_in_student.post("/submit_vote", data=choices)

    assert b"select a valid candidate for every position" in response.data
    assert system.ballots == {}


def test_voting_closed_prevents_vote(signed_in_student, system):
    system.settings["voting_open"] = "false"

    response = signed_in_student.post("/submit_vote", data=all_nota_choices())

    assert response.status_code == 302
    assert response.location.endswith("/vote")
    assert system.ballots == {}


def test_duplicate_vote_is_rejected(signed_in_student, system):
    system.ballots["A101"] = {"President": "NOTA"}

    response = signed_in_student.post("/submit_vote", data=all_nota_choices())

    assert response.status_code == 200
    assert system.ballots == {"A101": {"President": "NOTA"}}
    assert system.blockchain.pending_transactions == []


def test_ballot_storage_conflict_does_not_add_blockchain_entries(signed_in_student, system, monkeypatch):
    monkeypatch.setattr(voting_controller, "cast_ballot", lambda rollno, choices: False)

    response = signed_in_student.post("/submit_vote", data=all_nota_choices())

    assert response.status_code == 302
    assert system.blockchain.pending_transactions == []


def test_unapproved_student_session_is_cleared(signed_in_student, system):
    system.students["A101"]["approved"] = False

    response = signed_in_student.get("/vote")

    assert response.status_code == 302
    with signed_in_student.session_transaction() as session:
        assert "rollno" not in session


def test_logout_clears_student_session_and_protected_access(signed_in_student):
    assert signed_in_student.get("/logout").status_code == 302

    response = signed_in_student.get("/vote")

    assert response.status_code == 302
    with signed_in_student.session_transaction() as session:
        assert "rollno" not in session
        assert "pending_rollno" not in session