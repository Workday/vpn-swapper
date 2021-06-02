import logging
import sys
from logging import StreamHandler
from logging.handlers import RotatingFileHandler


def setup_logging(debug_level: bool, log_libraries: bool, logfile: str) -> None:

    # Remove all handlers associated with the root logger object.
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)

    # Choose logging configuration details
    conf = {}

    conf['format'] = '%(asctime)s %(name)s [%(filename)s:%(lineno)d] %(levelname)-8s %(message)s'
    conf['level'] = logging.DEBUG if debug_level else logging.INFO

    # If we want to use stdout, we already have a stream open for that...
    if not logfile or logfile == 'stdout':
        file_handler = StreamHandler(sys.stdout)
    # ...otherwise let logging do the file handling
    else:
        # 2^20 bytes = 1 MB
        mb = 2**20
        file_handler = RotatingFileHandler(filename=logfile, maxBytes=10*mb, backupCount=10)

    conf['handlers'] = [file_handler]

    logging.basicConfig(**conf)

    if not log_libraries:
        logging.getLogger("botocore").setLevel(logging.WARNING)
        logging.getLogger("paramiko").setLevel(logging.WARNING)
        logging.getLogger("urllib3").setLevel(logging.WARNING)
