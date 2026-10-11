import logging
import time

from nba_api.stats.library.http import NBAStatsHTTP

import config

logger = logging.getLogger(__name__)


def fetch(endpoint, **params):
    """Call an nba_api endpoint class with a polite delay and retries with backoff."""
    for attempt in range(1, config.MAX_RETRIES + 1):
        try:
            result = endpoint(timeout=config.REQUEST_TIMEOUT_SECONDS, **params)
            time.sleep(config.REQUEST_DELAY_SECONDS)
            return result
        except Exception as e:
            if attempt == config.MAX_RETRIES:
                raise
            wait = config.RETRY_BACKOFF_SECONDS * 2 ** (attempt - 1)
            logger.warning(f"{endpoint.__name__} {params} failed (attempt {attempt}): {e}. Retrying in {wait}s")
            time.sleep(wait)
            # nba_api reuses one HTTP session; after a few hundred requests stats.nba.com can
            # stop answering on it, so retry on a fresh connection.
            NBAStatsHTTP.set_session(None)
