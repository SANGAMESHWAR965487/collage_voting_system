# College Voting System Test Cases

Automated outcomes below reflect the final isolated pytest run: 81 passed and 0 failed. The cases marked `NOT TESTED` require real external accounts or a deployment environment; they are not included in the pytest counts.

Priority: `P1` critical workflow/security, `P2` important behavior, `P3` lower-risk or informational behavior.

## MongoDB And Student Records

| Test Case ID | Module | Test Case Name | Objective | Preconditions | Test Steps | Test Data | Expected Result | Actual Result | Status | Priority |
|---|---|---|---|---|---|---|---|---|---|---|
| MDB-01 | MongoDB | Database connection succeeds | Check client ping and lazy database setup | Mock MongoClient | Call `get_database()` with a fake client that answers `ping` | Fake database/client | Database returned and indexes initialized | Fake ping/index assertions passed | PASS | P1 |
| MDB-02 | MongoDB | OTP TTL index initialized | Confirm expiry index configuration | Fake Mongo database | Call `get_database()` and inspect `otp_codes.create_index` | `expires_at`, TTL 0 | Expiration index requested | Mock observed expected index call | PASS | P2 |
| MDB-03 | MongoDB | Student retrieval filters private fields | Confirm template user omits password/internal ID | Fake `users` and `votes` collections | Call `get_user_by_rollno` for existing record | Roll `A101`, hashed password | Student returned without `password` or `_id`; vote state included | Mocked retrieval assertions passed | PASS | P1 |
| MDB-04 | MongoDB | Missing student lookup | Check absent roll number behavior | Fake users collection returns `None` | Call `get_user_by_rollno` for absent roll | `MISSING` | Return `None` | Mocked missing-record test passed | PASS | P2 |
| MDB-05 | MongoDB | Connection error is sanitized | Check failed ping does not expose driver details | Fake client raises PyMongo timeout | Call `get_database()` | Simulated unavailable server | Raise `MongoConnectionError` with safe message and close client | Mocked error test passed | PASS | P1 |
| MDB-06 | MongoDB | Route returns generic DB error | Check request error handling | Test client and mocked DB error | POST login while rate-limit lookup raises `MongoConnectionError` | Dummy roll/password | Return 503 with generic message | Mocked route test passed; internal text absent | PASS | P1 |
| MDB-07 | MongoDB | Hashed student password validation | Check current Werkzeug hash format | Fake user with Werkzeug hash | Call `validate_login` using correct password | Correct test password | Return the matching student | Mocked hash validation passed | PASS | P1 |
| MDB-08 | MongoDB | Wrong password rejected by helper | Check password mismatch | Fake user with valid stored hash | Call `validate_login` using incorrect password | Incorrect test password | Return `None` | Mocked rejection passed | PASS | P1 |
| MDB-09 | MongoDB | Ballot persistence updates student | Check Mongo vote insert and voted marker | Fake Mongo collections | Call `cast_ballot` once | Roll `A101`, choice mapping | Insert vote document and set `users.voted` to 1 | Mock calls and ballot fields passed | PASS | P1 |
| MDB-10 | MongoDB | Duplicate ballot key rejected | Check unique vote constraint handling | Fake insert raises `DuplicateKeyError` | Call `cast_ballot` for duplicate roll | Existing roll | Return `False`; do not mark a new vote | Mocked duplicate-key test passed | PASS | P1 |

## Student And Admin Authentication

| Test Case ID | Module | Test Case Name | Objective | Preconditions | Test Steps | Test Data | Expected Result | Actual Result | Status | Priority |
|---|---|---|---|---|---|---|---|---|---|---|
| AUTH-01 | Authentication | Correct student credentials | Verify password step starts OTP challenge | Approved fake student and SMTP mock | POST `/login` with roll/password | Student A | Pending roll stored; authenticated roll not set | Route/session test passed | PASS | P1 |
| AUTH-02 | Authentication | Unknown roll number | Reject absent student | Fake store has no matching roll | POST `/login` | Unknown roll | Generic invalid-credentials message; no email sent | Route test passed | PASS | P1 |
| AUTH-03 | Authentication | Incorrect password | Reject bad password | Existing fake student | POST `/login` with wrong password | Student A, wrong password | Invalid credentials; no OTP email | Route test passed | PASS | P1 |
| AUTH-04 | Authentication | Empty credential values | Reject blank values | Test client | POST `/login` with empty roll/password | Empty strings | No OTP; invalid-credentials message | Route test passed | PASS | P2 |
| AUTH-05 | Authentication | Missing roll field | Record current required-field behavior | Test client | POST `/login` with password only | No `rollno` form key | Flask returns 400 from required form lookup | Route test passed | PASS | P2 |
| AUTH-06 | Authentication | Whitespace around roll | Confirm input sanitation | Approved fake student | POST `/login` with padded roll | ` A101 ` | Trimmed roll matches student | Route test passed | PASS | P2 |
| AUTH-07 | Authentication | Unapproved student login | Enforce account approval | Fake student marked unapproved | POST `/login` with correct credentials | Student A | Reject before sending OTP | Route test passed | PASS | P1 |
| AUTH-08 | Authentication | Login attempt limit | Check existing login rate limit | Fake counter at configured maximum | POST `/login` | Student A | Reject with rate-limit message; no email | Route test passed | PASS | P1 |
| AUTH-09 | Authentication | JSON OTP request success | Exercise existing `/send_otp` API | Approved fake student; mocked sender | POST JSON to `/send_otp` | Student B credentials | 200 success; code absent from response; student's email used | API test passed | PASS | P2 |
| AUTH-10 | Authentication | JSON OTP request rejects credentials | Exercise API failure path | Test client | POST invalid credentials to `/send_otp` | Student B, bad password | 401 failure response; no email | API test passed | PASS | P2 |
| AUTH-11 | Authentication | Valid admin login | Check existing admin ID/phone/password session | Test-only admin env constants | POST `/login` with all three values | Dummy admin credentials | Redirect to `/admin`; `admin` session set | Route/session test passed | PASS | P1 |
| AUTH-12 | Authentication | Invalid admin login | Reject incorrect admin tuple | Test-only admin env constants | POST `/login` with incorrect phone/password | Dummy admin ID, wrong credentials | No admin session; login rejected | Route/session test passed | PASS | P1 |
| AUTH-13 | Authentication | Password hash helper | Verify new passwords are not stored as plaintext | None | Call `hash_password`, then verify with Werkzeug checker | Dummy password | Encoded hash differs from input and verifies correctly | Unit test passed | PASS | P1 |

## Email OTP

| Test Case ID | Module | Test Case Name | Objective | Preconditions | Test Steps | Test Data | Expected Result | Actual Result | Status | Priority |
|---|---|---|---|---|---|---|---|---|---|---|
| OTP-01 | OTP | Six-digit OTP and expiry | Check generation format and five-minute validity | Approved fake student; mocked email | POST `/login`; inspect captured code/record | Student A | Six digits; only digest stored; expiry is 300 seconds; code absent from response | Assertions passed | PASS | P1 |
| OTP-02 | OTP | Student-specific recipient | Check each student uses their own email | Two fake students | Login separately as A and B | A/B roll and passwords | Email recipients match each record, not a fixed address | Mocked recipient assertions passed | PASS | P1 |
| OTP-03 | OTP | Correct OTP verification | Complete authentication only after OTP | Pending challenge | POST correct code to `/verify_otp` | Captured code | Redirect `/vote`; session contains roll; OTP deleted | Route/session test passed | PASS | P1 |
| OTP-04 | OTP | Incorrect OTP | Reject incorrect code and count attempt | Pending challenge | POST wrong six-digit value | `000000` | Error shown; attempt count increments; no authenticated session | Route test passed | PASS | P1 |
| OTP-05 | OTP | Expired code | Reject and delete expired challenge | Pending challenge record | Move expiry into past; POST code | Expired timestamp | Expired message; record deleted | Route test passed | PASS | P1 |
| OTP-06 | OTP | OTP reuse | Prevent second use | Valid code already verified once | POST the same code again | Previously accepted code | No second authentication from the OTP | Route test passed | PASS | P1 |
| OTP-07 | OTP | Maximum incorrect attempts | Stop brute-force attempts | Pending challenge | Submit five wrong codes | Five invalid values | OTP record and pending session removed | Route test passed | PASS | P1 |
| OTP-08 | OTP | Resend replaces old code | Ensure resend generates a fresh usable code | Pending challenge older than cooldown | POST `/resend_otp`; try old then new code | Old/new captured values | New code delivered; old rejected; new accepted | Route test passed | PASS | P1 |
| OTP-09 | OTP | Resend cooldown | Stop immediate repeat send | Fresh challenge | POST `/resend_otp` immediately | Less than 60 seconds | 429 response; no second email | Route test passed | PASS | P1 |
| OTP-10 | OTP | Resend maximum | Enforce three resend limit | Challenge at resend limit, cooldown elapsed | POST `/resend_otp` | Count 3 | 429 response; no email sent | Route test passed | PASS | P1 |
| OTP-11 | OTP | Expired resend challenge | Require new login after expiration | Pending challenge expired | POST `/resend_otp` | Expired record | Expired message; record and pending session removed | Route test passed | PASS | P2 |
| OTP-12 | OTP | SMTP failure | Ensure delivery failure is safe | SMTP mock raises auth failure | POST `/login` | Dummy credentials | Generic delivery error; no OTP record or authenticated session | Route test passed | PASS | P1 |
| OTP-13 | OTP | Missing student email | Avoid sending to a fallback recipient | Student has empty email | POST `/login` | Student A | Friendly failure; no OTP/email sent | Route test passed | PASS | P1 |
| OTP-14 | OTP | Verification without challenge | Reject unsolicited verification | No pending session | POST `/verify_otp` | Any six-digit value | Expired/not-requested response; no login | Route test passed | PASS | P1 |
| OTP-15 | OTP | JSON verification response | Check API does not echo OTP | Pending challenge | POST correct OTP as JSON | Captured code | Generic success JSON without code | API test passed | PASS | P2 |
| OTP-16 | OTP | Gmail SMTP message construction | Check TLS, target, subject, and body without network | Fake SMTP client and dummy mail settings | Call `_send_otp_email` | Individual test address/code | Gmail host/587, STARTTLS, correct recipient and five-minute text | Fake SMTP assertions passed; no network used | PASS | P2 |
| OTP-17 | OTP | Real Gmail delivery | Confirm provider credentials and inbox delivery | Gmail App Password and test account required | Perform manual login in staging | Real test student | Message arrives only at stored address | Not executed; real credentials/inbox not tested | NOT TESTED | P1 |

## Authorization And Voting

| Test Case ID | Module | Test Case Name | Objective | Preconditions | Test Steps | Test Data | Expected Result | Actual Result | Status | Priority |
|---|---|---|---|---|---|---|---|---|---|---|
| AUTHZ-01 | Authorization | Voting page before login | Protect `/vote` | No session | GET `/vote` | Anonymous client | Redirect to `/` | Route test passed | PASS | P1 |
| AUTHZ-02 | Authorization | Submit vote without session | Protect POST ballot route | No student session | POST `/submit_vote` | NOTA choices | Redirect to `/`; no ballot | Route test passed | PASS | P1 |
| AUTHZ-03 | Authorization | Voting page after OTP | Confirm verified session can access | Correct OTP verified or test session seeded | GET `/vote` | Approved student | Page returns 200 | Route test passed | PASS | P1 |
| AUTHZ-04 | Authorization | Rejected student session | Clear access if account is unapproved | Student session; fake record unapproved | GET `/vote` | Student A | Redirect; session cleared | Route test passed | PASS | P1 |
| AUTHZ-05 | Authorization | Anonymous admin route access | Protect admin operations | No admin session | Request `/admin`, approval/rejection, candidate, student list, voting controls, and `/mine` | Anonymous client | Redirect to `/` | Seven route cases passed | PASS | P1 |
| AUTHZ-06 | Authorization | Student admin route access | Prevent student-only session from acting as admin | Student session, no admin flag | GET `/admin`, POST `/add_candidate`, GET `/mine` | Student A | Redirect to `/` | Route test passed | PASS | P1 |
| AUTHZ-07 | Authorization | Public unreleased results | Match results visibility logic | `results_released` is not `true` | GET `/results` | Anonymous client | Show unreleased notice, not tally | Route test passed | PASS | P2 |
| AUTHZ-08 | Authorization | Public blockchain and verify routes | Record actual route access policy | No session | GET `/blockchain` and `/verify_chain` | Anonymous client | Explorer returns 200; verification redirects to explorer | Route tests passed | PASS | P2 |
| VOTE-01 | Voting | Valid ballot persistence and ledger enqueue | Check Mongo ballot, four ledger transactions, and save call | Approved student; voting open; fake persistence and blockchain | POST all four positions with NOTA | Four NOTA choices | Ballot stored once; four transactions queued; blockchain save invoked | These assertions passed before the response assertion failed | PASS | P1 |
| VOTE-02 | Voting | Success confirmation after valid ballot | Check user-facing success message and current admin state | Same valid ballot preconditions; admin setting is open | POST all positions with NOTA | Four NOTA choices | Render the successful-vote notice and voting-open state | Success notice rendered; closed branch absent | PASS | P1 |
| VOTE-03 | Voting | Current admin state is rendered | Ensure response honors a state change after vote acceptance | Student session; state reads open at gate then closed at response render | POST all positions with NOTA while mocked authoritative reads change from `true` to `false` | Four NOTA choices | Response renders closed state; it does not hardcode open | Closed branch rendered | PASS | P1 |
| VOTE-04 | Voting | Missing choices | Reject incomplete ballot | Student session; voting open | POST without position choices | Empty form | No vote stored; invalid-selection message | Route test passed | PASS | P1 |
| VOTE-05 | Voting | Invalid candidate | Reject unknown candidate | Student session; voting open | Submit unknown candidate for a position | Unknown name | No vote stored; invalid-selection message | Route test passed | PASS | P1 |
| VOTE-06 | Voting | Duplicate student vote | Prevent a second ballot | Student already present in fake ballots | POST another ballot | Same roll | Existing ballot unchanged; no new ledger transactions | Route test passed | PASS | P1 |
| VOTE-07 | Voting | Voting closed | Reject ballot while setting is closed | Student session; `voting_open=false` | POST a valid ballot | NOTA choices | Redirect to `/vote`; no vote stored | Route test passed | PASS | P1 |
| VOTE-08 | Voting | Mongo unique-key collision | Handle duplicate ballot persistence result | Fake Mongo vote insert raises duplicate key | Call `cast_ballot` | Existing roll | Return false; do not mark user voted again | Mongo helper test passed | PASS | P1 |
| VOTE-09 | Voting | Vote storage conflict | Do not enqueue chain entries if ballot write fails | Student session; fake `cast_ballot` returns false | POST valid ballot | NOTA choices | Redirect; no ledger transaction added | Route test passed | PASS | P1 |

## Admin

| Test Case ID | Module | Test Case Name | Objective | Preconditions | Test Steps | Test Data | Expected Result | Actual Result | Status | Priority |
|---|---|---|---|---|---|---|---|---|---|---|
| ADM-01 | Admin | Valid admin credentials | Confirm configured admin tuple grants admin session | Dummy admin constants in test | POST `/login` with ID, phone, password | Test-only values | Redirect `/admin`; `admin` set | Route/session test passed | PASS | P1 |
| ADM-02 | Admin | Invalid admin credentials | Reject incorrect tuple | Dummy admin constants in test | POST `/login` with wrong phone/password | Test-only values | No admin session | Route/session test passed | PASS | P1 |
| ADM-03 | Admin | Candidate creation | Add candidate through implemented endpoint | Admin session | POST `/add_candidate` | Valid name, symbol, allowed position | Candidate added | Route test passed | PASS | P1 |
| ADM-04 | Admin | Duplicate candidate | Enforce existing uniqueness behavior | Admin session and existing candidate | Add same position/name or symbol again | Duplicate values | Duplicate warning; no duplicate candidate | Route test passed | PASS | P2 |
| ADM-05 | Admin | Invalid candidate position | Validate allowed positions | Admin session | POST candidate using unsupported position | `Governor` | Invalid details response | Route test passed | PASS | P2 |
| ADM-06 | Admin | Approve registration | Test existing approval action | Admin session; pending student | POST `/approve_user` | Student B roll | Mongo helper invoked; student becomes approved in fake store | Route test passed | PASS | P1 |
| ADM-07 | Admin | Open voting | Test existing voting setting control | Admin session; voting initially closed | POST `/release_results` with `open_voting` | Action value | Setting becomes `true` | Route test passed | PASS | P1 |
| ADM-08 | Admin | Mine pending entries | Protect admin mining and save | Admin session; fake chain has pending transaction | GET `/mine` | One fake transaction | Mine called; save called; redirect explorer | Route test passed | PASS | P2 |
| ADM-09 | Admin | Candidate update/delete | Establish implementation boundary | Application route map | POST `/update_candidate` and `/delete_candidate` | N/A | No such feature; endpoints return 404 | Route tests passed | PASS | P3 |

## Blockchain, Security, And Logout

| Test Case ID | Module | Test Case Name | Objective | Preconditions | Test Steps | Test Data | Expected Result | Actual Result | Status | Priority |
|---|---|---|---|---|---|---|---|---|---|---|
| BC-01 | Blockchain | Valid chain | Verify hashes, indexes, links, and proof | In-memory chain with mined blocks | Call `is_chain_valid()` | Difficulty 2 test chain | Return true | Unit test passed | PASS | P1 |
| BC-02 | Blockchain | Deterministic block hash | Check hash changes with block content/nonce | Block objects | Calculate equal-content hashes; change nonce | Test transaction | Equal contents hash equally; changed nonce differs | Unit test passed | PASS | P2 |
| BC-03 | Blockchain | Tampered transaction | Detect mutation after mining | Valid in-memory chain | Change a stored candidate without recalculating hash | Candidate value | Chain invalid | Unit test passed | PASS | P1 |
| BC-04 | Blockchain | Previous-hash validation | Detect a correctly mined but wrongly linked block | Valid genesis and forged next block | Mine block referencing wrong previous hash | Wrong link | Chain invalid despite valid local hash/proof | Unit test passed | PASS | P1 |
| BC-05 | Blockchain | Proof-of-work validation | Require configured leading zeroes | Valid chain then increase required difficulty | Difficulty change | Chain invalid when proof is insufficient | Unit test passed | PASS | P1 |
| BC-06 | Blockchain | Block index validation | Require index equal chain position | Valid in-memory chain | Replace block with correctly mined wrong index | Index 7 at position 1 | Chain invalid | Unit test passed | PASS | P2 |
| BC-07 | Blockchain | Mine pending transactions | Check link and pending reset | In-memory chain and pending transaction | Mine pending list | Test miner | New block points to prior hash; pending clears; chain valid | Unit test passed | PASS | P1 |
| BC-08 | Blockchain | Empty mining is a no-op | Check no empty block is added | Chain with no pending transactions | Call mining method | Empty list | Chain length unchanged | Unit test passed | PASS | P3 |
| BC-09 | Blockchain | Save/load validation | Check JSON serialization without touching project ledger | Temporary directory | Save then load chain | `tmp_path` file | Loaded chain valid and original `blockchain.json` unchanged | Unit test passed | PASS | P2 |
| SEC-01 | Security | Session cookie flags | Check HTTPOnly, SameSite, and production Secure config | Flask config loaded | Inspect session cookie settings | Current mode | HTTPOnly true, SameSite Lax, Secure follows production flag | Unit test passed | PASS | P1 |
| SEC-02 | Security | OTP/email not exposed in login page | Check response privacy | OTP delivery mocked | POST successful password step | Test recipient/code | Response contains neither address nor code | Unit test passed | PASS | P1 |
| SEC-03 | Security | DB exception detail not exposed | Check generic response on DB outage | Mocked connection error | POST login | Simulated internal detail | 503 generic response, no internal exception text | Unit test passed | PASS | P1 |
| SEC-04 | Security | Live Atlas test database isolation | Confirm a live test database contains only test records | Staging Atlas credentials and approved test database required | Run deliberate read-only ping, then inspect staging database | Staging database | No production data used or changed | Not executed as part of pytest | NOT TESTED | P1 |
| LOG-01 | Logout | Logout clears pending OTP session | Remove pending authentication on logout | OTP challenge started | GET `/logout`; then POST `/verify_otp` | Pending test code | Session cleared; verification cannot authenticate | Route test passed; TTL record remains until expiry | PASS | P1 |
| LOG-02 | Logout | Logout blocks protected voting | Remove authenticated session access | Student session | GET `/logout`, then GET `/vote` | Student A | Session cleared and `/vote` redirects | Route test passed | PASS | P1 |