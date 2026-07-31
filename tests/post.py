# Standard library imports.
from datetime import datetime
import getpass
import logging
# import os
import platform
import sys
import uuid
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

# Related third party imports.
# (none)

# Local application/library specific imports.
# from . import central_logging
import central_logging


logger = logging.getLogger(__name__)


def get_http_handler_config_update():
    """Return a dict of handler config values from URL in sys.argv[1].

    Return a config dict of HTTP Handler config values with secure-flag, 
    host (or host:port), and path, specified by the URL in sys.argv[1].
    """

    assert len(sys.argv) == 2
    url_string = sys.argv[1]

    parsed_url = urlparse(url_string)

    # if parsed_url.scheme == 'http':
    #     secure = False
    # elif parsed_url.scheme == 'https':
    #     secure = True
    # else:
    #     sys.exit(f'Unsupported scheme: {parsed_url.scheme}')

    update = {
        'secure': True if parsed_url.scheme == 'https' else False,
        'host': parsed_url.netloc,
        'url': parsed_url.path if parsed_url.path else '/'
        }

    logger.debug('%s: %r', 'update', update)

    return update


def get_registration_info():
    """Return a dict of registration info."""
    info = {
        # 'name': None,
        # 'affiliation': None,
        # 'email': None,

        'name': 'James Stewart',
        'rank': 'Brigadier General',
        'serial number': 'O-433210',
        }

    # update reginfo dict with supplemental info from a survey of context
    info.update(get_context())

    info.update({'schema': 'reginfo 2026-02-20'})
    return info


def make_payload_with_context(payload):
    updated_payload = dict(payload)

    # update payload dict with supplemental info from a survey of context
    updated_payload.update(get_context())

    return updated_payload


def get_context():
    """Return a dict of context info."""
    return {
        'username': getpass.getuser(),

        'datetime': datetime.now(ZoneInfo('US/Eastern')).strftime(
            '%Y-%m-%dT%H:%M:%S%z'),
        'uuid': str(uuid.uuid4()),

        'platform': platform.platform(),
        'node': platform.node(),

        'version': None,
        }


if __name__ == '__main__':
    # logging.basicConfig(level=logging.INFO)
    logging.basicConfig(
        level=logging.DEBUG,
        datefmt='%Y-%m-%d %H:%M:%S',
        # datefmt='%H:%M:%S',
        format='\t'.join([
            '%(asctime)s',
            '%(levelname)s',
            # '[%(name)s:%(module)s:%(lineno)d]',
            '[%(module)s:%(lineno)d]',
            '%(message)s',
            ])
        )

    central_logger = central_logging.get_central_logger(
        http_handler_config_update=get_http_handler_config_update(),
        )

    assert isinstance(central_logger.disabled, bool)
    if central_logger.disabled is True:
        logger.info('Central Logging is disabled.')
    else:
        logger.info('Central Logging is enabled.')

    # Report status (e.g. sw start, feature use) and context to the 
    # central receiver.
    # if central_logger.disabled is True, no logrecord is created/sent.
    payload = make_payload_with_context({
        'milestone': 'App started',
        'schema': 'usage 2026-02-20',
        })
    logger.info('%s: %r', 'payload', payload)
    central_logger.info(payload)
    
    # Report registration info
    reginfo = get_registration_info()
    logger.info('%s: %r', 'reginfo', reginfo)
    central_logger.info(reginfo)
