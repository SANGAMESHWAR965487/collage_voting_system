import pytest

import app as voting_app


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("get", "/admin"),
        ("post", "/approve_user"),
        ("post", "/reject_user"),
        ("get", "/registered_students"),
        ("post", "/add_candidate"),
        ("post", "/release_results"),
        ("get", "/mine"),
    ],
)
def test_student_or_anonymous_request_cannot_use_admin_routes(client, method, path):
    response = getattr(client, method)(path, data={})

    assert response.status_code == 302
    assert response.location.endswith("/")


def test_authenticated_student_cannot_use_admin_routes(signed_in_student):
    for path, method in (("/admin", "get"), ("/add_candidate", "post"), ("/mine", "get")):
        response = getattr(signed_in_student, method)(path, data={})
        assert response.status_code == 302
        assert response.location.endswith("/")


def test_admin_can_create_candidate(admin_client, system):
    response = admin_client.post("/add_candidate", data={
        "candidate_name": "Alex Example",
        "candidate_symbol": "Star",
        "position": "President",
    })

    assert b"Candidate Added Successfully" in response.data
    assert system.candidates["President"][0]["name"] == "Alex Example"


def test_duplicate_candidate_is_rejected(admin_client):
    payload = {
        "candidate_name": "Alex Example",
        "candidate_symbol": "Star",
        "position": "President",
    }
    admin_client.post("/add_candidate", data=payload)

    response = admin_client.post("/add_candidate", data=payload)

    assert b"Symbol already used in this position" in response.data


def test_invalid_candidate_position_is_rejected(admin_client):
    response = admin_client.post("/add_candidate", data={
        "candidate_name": "Alex Example",
        "candidate_symbol": "Star",
        "position": "Governor",
    })

    assert b"Invalid candidate details" in response.data


def test_candidate_update_and_delete_routes_are_not_implemented(client):
    assert client.post("/update_candidate").status_code == 404
    assert client.post("/delete_candidate").status_code == 404


def test_admin_can_approve_student(admin_client, system):
    system.students["B202"]["approved"] = False

    response = admin_client.post("/approve_user", data={"rollno": "B202"})

    assert response.status_code == 302
    assert system.students["B202"]["approved"] is True


def test_admin_can_open_voting(admin_client, system):
    system.settings["voting_open"] = "false"

    response = admin_client.post("/release_results", data={"action": "open_voting"})

    assert response.status_code == 200
    assert system.settings["voting_open"] == "true"


def test_admin_can_mine_pending_blockchain_entries(admin_client, system):
    system.blockchain.pending_transactions.append({"position": "President", "candidate": "NOTA"})

    response = admin_client.get("/mine")

    assert response.status_code == 302
    assert response.location.endswith("/blockchain")
    assert system.blockchain.mined == 1
    assert system.blockchain.saved == 1


def test_results_route_shows_unreleased_state_to_public(client, system):
    response = client.get("/results")

    assert response.status_code == 200
    assert b"Results Not Released Yet" in response.data


def test_blockchain_explorer_is_public(client):
    response = client.get("/blockchain")

    assert response.status_code == 200
    assert b"Blockchain Explorer" in response.data


def test_public_chain_verification_route_redirects(client):
    response = client.get("/verify_chain")

    assert response.status_code == 302
    assert response.location.endswith("/blockchain")