import logging
import logging.handlers

def reset_central_logger(logger):
    """Reset the Central Logger.  (Useful during interactive dev.)"""
    assert logger.name == 'Central Logger'
    if hasattr(logger, 'configured'):
         delattr(logger, 'configured')

    logger.setLevel(logging.NOTSET)

    for h in logger.handlers:
        logger.removeHandler(h)

    logger.propagate = True


def get_central_logger(reset=False):
    """Return logger 'Central Logger', configured to send to an HTTP server.

    Return logger 'Central Logger', configured to send log records to an 
    HTTP server.
    
    Weakness:  This implementation uses an HTTPHandler, which waits 
        for the send to complete (or timeout).
        Consider using QueueHandler/QueueListener and
        multiprocessing.Queue to let handlers do their work on a 
        separate thread. 

    References 
    [1] search: python logging send to url http post
        https://www.google.com/search?q=python+logging+send+to+url+http+post

        "Python's built-in logging module can send log records to an HTTP
        server using the HTTPHandler class. This allows for centralized 
        log management by sending logs to a remote endpoint."

    Dev 
        import mylogging
        import importlib
        importlib.reload(mylogging)
        central_logger = mylogging.get_central_logger(reset=True)
    """

    central_logger = logging.getLogger('Central Logger')

    if reset:
        reset_central_logger(central_logger)

    if getattr(central_logger, 'configured', False):
        return central_logger

    # Milepost: central_logger has not been configured yet.
    central_logger.setLevel(logging.INFO)

    # Prepare a handler.
    # An HTTPHandler doesn't use a Formatter, so using setFormatter() to 
    # specify a Formatter for an HTTPHandler has no effect.
    http_handler = logging.handlers.HTTPHandler(
        # host='your_server.com:8000',  # Host and optional port
        # url='/log_endpoint',         # URL path on the server

        host='solid-skill-463519-e0.appspot.com',
        # secure=True,                 # Use HTTPS if needed
        # host='localhost:8080',
        secure=False,                 # Use HTTPS if needed

        url='/',
        method='POST',               # Specify POST method

        # credentials=('username', 'password') # Optional basic authentication
        )

    # Add the handler to the logger
    central_logger.addHandler(http_handler)

    # during dev, consider 
    #     add a shadow handler, or, set propagate to True
    #     logging.raiseExceptions=True
    #
    # # if config dir exists so that logfile can be written...
    # h2 = logging.FileHandler(
    #     os.path.join(os.path.expanduser('~'), '.mydev.centrallogger.log'),
    #     mode='a')
    # h2.setFormatter(f)
    # central_logger.addHandler(h2)

    central_logger.configured = True
    return central_logger

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)

    central_logger = get_central_logger()

    reginfo = {
        'name': 'James Stewart', 
        'rank': 'Brigadier General',
        'serial number': 'O-433210',
        'vicelist': [None, True],
        }

    central_logger.info(reginfo)
    # central_logger.info('yabba')
