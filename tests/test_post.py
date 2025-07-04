import logging
import sys

import central_logging


logging.basicConfig(level=logging.INFO)


if __name__ == '__main__':
    if '--local' in sys.argv and '--gcp' not in sys.argv:
        http_handler_config = {
            # Host and optional port
            'host': 'localhost:8080',
            }
    elif '--local' not in sys.argv and '--gcp' in sys.argv:
        http_handler_config = {
            # Host and optional port
            'host': 'solid-skill-463519-e0.appspot.com',  
            }
    else:
        sys.exit("bad usage... specify '--local' or '--gcp'")

    http_handler_config.update({
        'url': '/',  # URL path on the server
        'secure': True,  # Use HTTPS if needed
        'method': 'POST',  # Specify POST method
    
        # Optional basic authentication
        # 'credentials': ('username', 'password'),  
        })

    central_logger = central_logging.get_central_logger(http_handler_config)

    reginfo = {
        'name': 'James Stewart', 
        'rank': 'Brigadier General',
        'serial number': 'O-433210',
        }

    logging.info(reginfo)
    central_logger.info(reginfo)
