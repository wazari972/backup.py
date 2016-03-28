#! /usr/bin/python3

"""Backup tool

Usage:
  backup.py init <name> [--force]
  backup.py init from <name> as <backup-name> [--force]
  backup.py update [--checksum]
  backup.py status [--force] [--checksum]
  backup.py status [show|verify|clean]
  backup.py treat new [--delete]
  backup.py treat (missing|updated|moved|all)
  backup.py config 
  backup.py debug info
  backup.py (-h | --help)

Options:
  -v, --verbose    Print more text.
"""

from docopt import docopt

import os, sys, traceback
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
log = logging.getLogger('backup.dispatch')

import init, config, status, verify, info, update, treat

def main(args):
    try: os.mkdir(config.CONFIG_PATH)
    except FileExistsError: pass # ignore

    try:
        if config.NOP:
            log.critical("************************")
            log.critical("*** NOP mode active. ***")
            log.critical("************************")
        #################
        if args["init"]:
            init.do_init(args)
            
        elif args["update"]:
            update.do_update(args)
            
        elif args["status"]:
            status.do_status(args)

        elif args["treat"]:
            treat.do_treat(args)
            
        elif args["config"]:
            log.warn("cannot configure yet")
            
        elif args["debug"] and args["info"]:
            info.do_info(args)
        else:
            print(__doc__)
    except Exception as e:
        PRINT_EXCEPTION = True
        START_PDB = True
        
        if START_PDB:
            type, value, tb = sys.exc_info()
            traceback.print_exc()
            import pdb; pdb.post_mortem(tb)
        elif PRINT_EXCEPTION:
            traceback.print_exc()
        else:
            log.critical("Critical failure, bye ...")
            log.critical(e)
    finally:
        
        # print("---")
        # print("  "+"\n  ".join("{:10s}->  {}".format(k, v) for k, v in args.items() if v))
        # print("---")
        # print("  "+"\n  ".join("{:10s}->  {}".format(k, v) for k, v in args.items() if not v))
        if config.NOP:
            log.critical("************************")
            log.critical("*** NOP mode active. ***")
            log.critical("************************")
            
if __name__ == '__main__':
    main(docopt(__doc__, version='backup.py 0.9'))
        
