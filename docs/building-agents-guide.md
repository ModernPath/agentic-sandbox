# Building an agent: a guide for people who are not developers

An **agent** is a small add-on to the sandbox that does one job for your team, such as preparing a brief before a meeting or keeping track of competitor news. You describe what it should do. An AI coding assistant helps you build it. A developer checks the work before it goes into the shared code.

This guide is for you if you know your business problem well but have not built software before. Read it top to bottom once. After that, use the steps as a checklist.

## Who does what

| Role | Who | What they do |
|---|---|---|
| **Requester** | Anyone on the team | Describes the agent with the request form. Answers the questions about data and risk. |
| **Builder** | You, with an AI coding assistant | Turns the answers into specification files, builds the agent, and runs the tests. |
| **Reviewer** | A developer | Checks the change against the checklist in the pull request, then merges it. |

Most agents need one builder and one reviewer. The reviewer is not optional.

## Before you start

You need:

- Access to the GitHub repository (ask the developer to add you).
- A computer where the developer has installed Python 3.12, Git, and this repository. Ask for a short setup session the first time.
- An AI coding assistant that can run commands in the project folder. The repository's `AGENTS.md` file tells the assistant the rules.

You do **not** need to write code yourself. You do need to read what the assistant produces and answer questions about your business.

## The five steps

### 1. Describe the agent

Open a new issue on GitHub using the **Agent request** template. It asks the questions in `specs/templates/agent-request.md`. Be concrete. For example: "Before a sales meeting, I want a one-page brief on the company, with recent news and sources."

Answer the data questions carefully. They decide what the agent may store, how long, and what it may send to outside providers.

### 2. Turn the answers into specifications

Give the issue to your AI coding assistant and ask it to create the specification files for the agent, following `specs/templates/agent-request.md` and the example in `specs/features/meeting-prep/`. Read the three files it creates:

- `task_spec.md`: what the agent does, and how you will know it works.
- `technical_spec.md`: how it is built, how long it keeps data, and what it costs.
- `test_plan.md`: the checks that prove it works.

If something is unclear, say so and ask again. A specification that is wrong now costs much more later.

### 3. Create the agent

Ask the assistant to run the scaffold from the project folder:

```sh
python -m sandbox_host.scaffold your_agent_name --description "One sentence about what it does"
```

Use lowercase letters and underscores for the name, for example `deal_notes`. The command creates a folder `agents/your_agent_name/` with the standard files and adds the agent to `sandbox_app.py`.

### 4. Build it, with the tests first

The assistant writes a failing test for each behaviour, then the code that makes it pass. You can check the progress with:

```sh
PYTHONPATH=src:agents python -m pytest -q agents/your_agent_name/tests
```

You want to see `passed` and no `failed` or `error`. If you see errors, paste the last lines to the assistant and ask it to fix them. Do not ask it to remove a test because it fails.

### 5. Try it, then open a pull request

Start the sandbox on your computer and open it in a browser. Ask the developer for the start command the first time. Run the agent once with realistic but **made-up** data. Note what worked and what did not.

Then ask the assistant to commit the changes and open a pull request, using the pull-request template. A reviewer checks it before anything is merged.

## What you can change yourself, and what needs a developer

**You can change yourself**, in your agent's own folder:

- The wording of the agent's instructions, its summaries, and its screens.
- The list of things it checks or looks for, as long as the tests still pass.
- The notes and examples in its documentation.

**Ask a developer first:**

- Anything in the shared host, the database structure used by several agents, or the sign-in system.
- A new outside provider, or a new key.
- Anything that sends messages, emails, or posts outside the sandbox.
- Deleting or exporting real data.
- Putting anything on a server or changing who can sign in.

## Never do these

- **Never paste an API key, password, or token** into the chat, an issue, a file, or a commit. Keys go in the environment file on the developer's computer, which Git ignores. If a key was pasted by mistake, tell a developer straight away so it can be replaced.
- **Never use real client data in tests, examples, or screenshots.** Use made-up names and numbers.
- **Never make an agent send something to a person without approval.** Outgoing messages are drafts that someone approves. This rule applies even in test setups.
- **Never ask the assistant to skip the tests** or to make them pass by changing what they check.
- **Never merge your own pull request.**

## How to tell it is ready for review

- The agent's tests pass, and the full test suite still passes.
- You ran the agent once with made-up data and the result matches the specification.
- The specification says how long data is kept and what leaves the sandbox.
- The pull request lists the risks in its description, and the reviewer checklist is complete.

## Words you will see

- **Agent:** a self-contained piece that does one job, with its own folder.
- **Host:** the shared part of the sandbox that signs people in and stores data.
- **Specification (spec):** the written description of what an agent does, in three files.
- **Test:** a check that runs automatically and fails if the agent stops doing what its specification says.
- **Migration:** a recorded change to the database structure. Migrations are added, never edited.
- **Provider:** an outside service the sandbox uses, such as a language model or a web search service.
- **Key:** a secret password for a provider. Never share one.
- **Pull request:** a proposed change to the shared code, reviewed before it is merged.

## A worked example

`specs/features/meeting-prep/` is a complete agent written this way. Read its three files to see what a finished specification looks like. The agent's code is in `agents/meeting_prep/`.
