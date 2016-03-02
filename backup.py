#! /usr/bin/python3

"""Backup tool

Usage:
  backup.py init <name> [--force]
  backup.py init from <name> as <backup-name> [--force]
  backup.py update [--checksum]
  backup.py status [--checksum]
  backup.py status verify
  backup.py status clean
  backup.py treat new|missing|updated|all
  backup.py debug info
  backup.py (-h | --help)

Options:
  -v, --verbose    Print more text.
"""

from docopt import docopt

import os, sys
import logging as log

from enum import Enum
import traceback

import logging

def init_logging():
    LOG_LEVEL = logging.DEBUG
    LOGFORMAT = "  %(log_color)s%(levelname)-8s%(reset)s | %(log_color)s%(message)s%(reset)s"
    from colorlog import ColoredFormatter
    logging.root.setLevel(LOG_LEVEL)
    formatter = ColoredFormatter(LOGFORMAT)
    stream = logging.StreamHandler()
    stream.setLevel(LOG_LEVEL)
    stream.setFormatter(formatter)

    log = logging.getLogger('backup')
    log.setLevel(LOG_LEVEL)
    log.addHandler(stream)

    return log


init_logging()
log = logging.getLogger('root')

import init, config, status, verify, info, update, treat

def main(args):
    try: os.mkdir(config.CONFIG_PATH)
    except FileExistsError: pass # ignore

    try:            
        #################
            
        if args["init"]:
            init.do_init(args)
            
        elif args["update"]:
            update.do_update(args)
            
        elif args["status"]:
            status.do_status(args)

        elif args["treat"]:
            treat.do_treat(args)
            
        elif args["debug"] and args["info"]:
            info.do_info(args)
        else:
            print(__doc__)
    except Exception as e:
        log.critical(e)
        traceback.print_exc()
    finally:
        pass
        # print("---")
        # print("  "+"\n  ".join("{:10s}->  {}".format(k, v) for k, v in args.items() if v))
        # print("---")
        # print("  "+"\n  ".join("{:10s}->  {}".format(k, v) for k, v in args.items() if not v))
            
if __name__ == '__main__':
    main(docopt(__doc__, version='backup.py 0.9'))
