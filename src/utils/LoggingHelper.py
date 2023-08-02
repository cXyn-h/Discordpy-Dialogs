import logging
import sys

def use_default_setup(logger):
    '''makes sure there's the logger passed in is uses this repo's default settings for logging: one handler printing to stdout and special format'''
    if not logger.hasHandlers():
        logging_handler = logging.StreamHandler(sys.stdout)
        logging_format = logging.Formatter('[{asctime}] [{levelname:<8}] {name}: {message}', '%Y-%m-%d %H:%M:%S', style='{')
        logging_handler.setFormatter(logging_format)
        logger.addHandler(logging_handler)
