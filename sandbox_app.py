"""Composition root for this sandbox: the one place that decides which agents run.

Add an agent by importing its spec and appending it to AGENTS. Run with:

    PYTHONPATH=src:agents .venv/bin/uvicorn sandbox_app:create_sandbox_app --factory
"""

from sandbox_host.app import create_app
from sandbox_host.config import HostSettings
from sandbox_host.database import make_engine
from emeia_dashboard.api import make_agent_spec as make_dashboard_spec
from file_reader.api import make_agent_spec as make_file_reader_spec
from competitor_watch.api import make_agent_spec as make_competitor_watch_spec
from research_brief.api import make_agent_spec
# <scaffold:imports>
from meeting_prep.api import make_agent_spec as make_meeting_prep_spec

AGENTS = [
    make_agent_spec(),
    make_dashboard_spec(),
    make_file_reader_spec(),
    make_competitor_watch_spec(),
    # <scaffold:agents>
    make_meeting_prep_spec(),
]


def create_sandbox_app():
    settings = HostSettings.from_env()
    engine = make_engine(settings.database_url) if settings.database_url else None
    return create_app(settings, agents=AGENTS, engine=engine)
