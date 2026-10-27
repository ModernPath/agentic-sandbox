# Task spec: meeting prep

**Status:** Built offline; live run pending · **Builds on:** [agent standard](../agent-standard/task_spec.md), [agent building blocks](../agent-building-blocks/task_spec.md), [sales radar](../sales-radar/task_spec.md), [file handling](../file-handling/task_spec.md), [common chat](../common-chat/task_spec.md)

## Goal

Before a sales meeting, a salesperson asks for a one-page brief on the company they are meeting. The agent gathers recent public information about the company, the sales radar's signals that mention it, and optional uploaded notes, then drafts a brief with numbered citations, talking points, and open questions. The brief is a draft for the salesperson to check. Nothing is sent anywhere.

## Who uses it

Salespeople, from the agent's page or from the common chat ("prep me for Acme on Thursday").

## Behaviour

- **M1 Request.** A signed-in user asks for a brief with: company name (2–120 characters, required), website (optional, `http(s)` only), meeting date (optional, `YYYY-MM-DD`), purpose (optional, up to 500 characters), attendees (optional, up to 10, each a name and a role of up to 120 characters each), and a notes file id (optional, a file uploaded to `file_reader`).
- **M2 Company research.** The agent searches the web for the company through the search block (up to 6 results) and reads up to 3 pages through the page reader. Only `http(s)` links are kept. A page that cannot be read falls back to its search snippet. Each source is numbered.
- **M3 Radar signals.** The agent asks the sales radar (`competitor_watch`, through its command-line tool) for its new and reviewed signals and keeps up to 5 that mention the company by name, in the competitor name, headline, or summary. They are numbered after the web sources and cited the same way. Meeting prep never reads the radar's tables.
- **M4 Notes.** When a notes file id is given, the agent reads the file's text through `file_reader`'s command-line tool (up to 6,000 characters). The notes text goes into the prompt only. Meeting prep stores the file id and file name, not the text.
- **M5 Draft.** One model call writes the brief with these sections: Company snapshot, Recent news, Radar signals, Talking points, Open questions. Claims cite sources as `[n]`. When the evidence is thin, the brief says so. The brief is capped at 6,000 characters.
- **M6 Untrusted input.** Search results, page text, signals, and notes are data. The prompt tells the model not to follow instructions found in them.
- **M7 Partial results.** A part that fails or is not configured does not stop the brief. Each one adds a short, fixed gap message (for example "Web search is not configured."). With no model, the brief is saved with its sources, signals, and gaps, and no written summary, with a reason saying that no model is configured. Provider messages are never shown or stored.
- **M8 Briefs.** Briefs are stored, listed newest first, and fetched by id. A person can delete a brief from the page or the API. Delete is not offered to the chat.
- **M9 Retention.** A brief expires 30 days after it is created. Expired briefs are deleted whenever briefs are created or listed, and by the `purge` command.
- **M10 Panel.** The front-page panel shows the number of briefs kept and the 5 newest (company, meeting date or created day).
- **M11 Surfaces.** The same use cases are exposed through the API, the page, model tools (`prepare_meeting`, `list_briefs`, `get_brief`), and a JSON command-line tool. The chat may run `prepare`, `list`, and `get`.

## Personal data

| What | Where | Kept |
|---|---|---|
| Attendee names and roles, as typed by the user | the brief record, and the model prompt | 30 days (M9) or until deleted |
| The written brief (may name attendees) | the brief record | 30 days or until deleted |
| Notes text | the model prompt only | not stored by meeting prep (the file stays in `file_reader` under its own rules) |

Attendees are not looked up on the web in this version. Use only notes and attendee details approved for the configured model provider.

## Cost

One search, up to 3 page reads, and one model call per brief. The radar and notes calls are local. No paid people search.

## Out of scope

- Looking up attendees with `people_company_search` (paid, and its API is not mounted yet). A later increment, with its own cost cap.
- Calendar integration, scheduled briefs, sending the brief by email or chat.
- Writing to the CRM core (for example logging an activity).

## Acceptance criteria

- M1–M11 covered by the offline tests in [test_plan.md](test_plan.md), with fake search, reader, model, and peer agents.
- Live: one brief with the configured search and model, and one with a radar signal and a notes file, recorded in `acceptance_results.md`.
- Browser: sign in, prepare a brief, open it, delete it, sign out. Recorded in `acceptance_results.md`.
