"""Git sync: commit notes and push to remote on interval."""
from __future__ import annotations

import logging
from datetime import datetime

logger = logging.getLogger(__name__)


def commit_note(vault_path: str, file_path: str, config) -> None:
    """Stage file and commit to vault git repo."""
    try:
        from git import InvalidGitRepositoryError, Repo
        repo = Repo(vault_path)
        repo.index.add([file_path])
        now = datetime.now()
        message = config.commit_message.format(
            date=now.strftime("%Y-%m-%d"),
            time=now.strftime("%H:%M"),
        )
        repo.index.commit(message)
    except Exception as exc:
        logger.warning("git commit_note failed: %s", exc)


def push_if_due(vault_path: str, config, last_push: datetime) -> datetime:
    """Push to remote if push_interval_minutes elapsed. Returns updated last_push on success."""
    elapsed_minutes = (datetime.now() - last_push).total_seconds() / 60
    if elapsed_minutes < config.push_interval_minutes:
        return last_push
    try:
        from git import Repo
        repo = Repo(vault_path)
        origin = repo.remote(config.remote)
        origin.push(config.branch)
        logger.info("git push to %s/%s succeeded", config.remote, config.branch)
        return datetime.now()
    except Exception as exc:
        logger.warning("git push failed (continuing): %s", exc)
        return last_push
