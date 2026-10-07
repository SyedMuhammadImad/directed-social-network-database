# Directed social-network database project

A completed local SQLite/SQLAlchemy example: import members and clubs, query club membership, distinguish outgoing friends from people who consider someone a friend, and replace the dataset atomically. It is demonstration database project, not a hosted social network.

## Run

Use Python 3.12, install `requirements.txt`, then:

```text
python -m pytest -q
python social_database.py
python social_database.py --csv /path/to/members.csv
```

The default command imports three fictional records into an in-memory database and prints counts: three people, two clubs, three directed friendships and three club memberships. No real member records, database binaries, credentials or media are committed. `example_members.csv` is explicitly synthetic; the original reference CSV and platform grader were not available. No official reference grade is claimed.

For programmatic file persistence, pass a local SQLite URL to `create_database(database_url)`. Opening a database does not delete its file. Its returned session and model/table handles work with `load_data_from_csv`; pass the CSV path explicitly. The import replaces the project graph only, after all CSV validation has succeeded. Commit unrelated pending session changes before importing. Close the session and dispose its engine after use.

## Data and behavior

CSV columns must be `ID,Name,Surname,Age,Gender,Location,Clubs,Friendships` in that order. `Clubs` is a literal list of descriptions and `Friendships` a literal list of positive integer IDs. List parsing does not execute expressions. All referenced IDs must exist; IDs must be unique; ages must be 0–130. Self friendships are rejected. Duplicate club/friend entries collapse to one relationship. Empty input clears the project graph. Queries return deterministic ID order and empty lists for missing matches. Full-name queries reject ambiguity rather than silently select a person.

Imports validate the whole bounded CSV before deleting anything. Foreign keys and constraints are active. Association rows are replaced before people/clubs; any database failure rolls back the complete import. This improves the original example's hardcoded file path, unsafe expression evaluation, early commits and destructive database initialization. Validation is intentionally scoped to this local demonstration schema, not authentication or enterprise privacy controls.

## Notebook and tests

The notebook follows setup → import → queries → verification, using only the fictional fixture. Independent tests cover directed relationships, missing queries, idempotent/replacement imports, empty input, malformed lists, duplicate IDs, missing references, active constraints, ambiguous names, file persistence and rollback after an injected database failure. See `VERIFICATION.json` and `ATTRIBUTION.md`.
