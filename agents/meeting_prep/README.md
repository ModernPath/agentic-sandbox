# meeting_prep

A one-page brief before a sales meeting: recent public news with numbered citations, sales radar signals that mention the company, notes from an uploaded file, talking points, and open questions. Briefs are drafts. Check every citation before use. Nothing is sent anywhere.

## Contract

- **Users:** signed-in sandbox users, on `/agents/meeting-prep/` or through the common chat.
- **Inputs:** company (required), website, meeting date, purpose, up to 10 attendees (name and role), and an optional `file_reader` file id for notes.
- **Outputs:** a stored brief: written summary (or a reason why there is none), numbered sources (web and radar), matched radar signals, and gap messages for parts that were unavailable.
- **Data:** table `meeting_prep_briefs` only. Attendee names are stored with the brief. Briefs expire after 30 days. Notes text is not stored.
- **Side effects:** one web search, up to 3 page reads, and one model call per brief. Runs `competitor_watch.cli signals` and `file_reader.cli read` as subprocesses. Never publishes or sends.
- **Blocks used:** search, page reader, LLM (all optional; missing ones become gaps).
- **Configuration:** the host's `DATABASE_URL` and the `SANDBOX_*` provider variables. Nothing of its own.

## API

| Method | Path | |
|---|---|---|
| POST | `/api/agents/meeting-prep/briefs` | prepare a brief |
| GET | `/api/agents/meeting-prep/briefs` | list, newest first |
| GET | `/api/agents/meeting-prep/briefs/{id}` | one brief |
| DELETE | `/api/agents/meeting-prep/briefs/{id}` | delete (a person, from the page) |
| GET | `/api/agents/meeting-prep/panel` | front-page panel |

## CLI

```
python -m meeting_prep.cli prepare --company "Acme Oy" --date 2026-10-30 --attendees "Ana Silva (CTO); Ben Ode"
python -m meeting_prep.cli list
python -m meeting_prep.cli get --id ID
python -m meeting_prep.cli delete --id ID
python -m meeting_prep.cli purge
```

The chat may run `prepare`, `list`, and `get`. Model tools: `prepare_meeting`, `list_briefs`, `get_brief`.

## Tests

```
PYTHONPATH=src:agents python -m pytest -q agents/meeting_prep/tests
```
