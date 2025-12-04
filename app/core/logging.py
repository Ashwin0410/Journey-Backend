import logging, sys

def setup():
    log = logging.getLogger()
    log.setLevel(logging.INFO)
    h = logging.StreamHandler(sys.stdout)
    fmt = logging.Formatter("[%(asctime)s] [%(levelname)s] %(message)s")
    h.setFormatter(fmt)
    log.handlers.clear()
    log.addHandler(h)
