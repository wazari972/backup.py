#! /usr/bin/python3

"""Backup tool

Usage:
  backup.py create [--db=<db.txt>] [--fs=<local>]
  backup.py check (local | external | rsync | <path>) [--db=<db.txt>]
  backup.py (-h | --help)
  backup.py [--verbose | -v | -vv | -vvv]
  
Options:
  -v, --verbose    Print more text
"""

from docopt import docopt

import os, sys
import logging as log
import hashlib
from enum import Enum
import traceback

import logging

def init_logging():
    LOG_LEVEL = logging.CRITICAL
    LOGFORMAT = "  %(log_color)s%(levelname)-8s%(reset)s | %(log_color)s%(message)s%(reset)s"
    from colorlog import ColoredFormatter
    logging.root.setLevel(LOG_LEVEL)
    formatter = ColoredFormatter(LOGFORMAT)
    stream = logging.StreamHandler()
    stream.setLevel(LOG_LEVEL)
    stream.setFormatter(formatter)

    log = logging.getLogger('root')
    log.setLevel(LOG_LEVEL)
    log.addHandler(stream)

    return log

log = init_logging()


TO_IGNORE = [".git", "Other", "tmp", "VIDEO"]

NEW_FILES = "new.txt"
MISSING_FILES = "missing.txt"
DIFFERENT_FILES = "different.txt"
GOOD_FILES = "good.txt"

STARTUP_CLEANING = MISSING_FILES, DIFFERENT_FILES, NEW_FILES, GOOD_FILES

def progress(current, total):
    sys.stdout.write("\r%.2f%%" % (current/total*100))
    sys.stdout.flush()

class Checksym(Enum):
    MD5_FILE = 1

CHKSUM_ALGO = True # or None
    
def checksum(fname):
    if not CHKSUM_ALGO:
        return "0"
    
    hashval = hashlib.md5()
        
    with open(fname, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hashval.update(chunk)
            
    return hashval.hexdigest()

def db_length(db_fname):
    with open(db_fname) as db_f:
        return len(db_f.readlines())
        
def browse_db(db_fname):
    with open(db_fname) as db_f:
        for line in db_f.readlines():
            relpath, _, info_txt = line[:-1].partition(" -> ")
            info_lst = info_txt.split(", ")
            info = {item.split(": ")[0]: item.split(": ")[1] for item in info_lst}

            yield relpath, info

def browse_filesystem(fs_dir):
    for dirpath, dirnames, files in os.walk(fs_dir):
        
        for ign in TO_IGNORE:
            try:
                dirnames.remove(ign)
            except ValueError: pass # ign was not in the list
        dirnames.sort()
        files.sort()

        for name in sorted(files):
            fullpath = os.path.join(dirpath, name)

            relpath = fullpath[len(fs_dir)+1:]

            st = os.stat(fullpath)
            
            info = {
                "filesum" : checksum(fullpath),
                "size" : str(st.st_size)
                #, "mtime" :  str(st.st_mtime)
                }

            yield fullpath, relpath, info
        yield None

def print_filesystem(fs_dir, out_f=sys.stdout):
    for a_file in browse_filesystem(fs_dir):
        if a_file is None:
            if out_f == sys.stdout:
                print("---")
            continue
        fullpath, relpath, info = a_file
        print("{} -> {}".format(fullpath.replace(fs_dir+"/", ""),
                                ", ".join([ "{}: {}".format(k, v) for k,v in info.items()])),
              file=out_f)

def create_database(db_file, fs_dir):
    with open(db_file, "w+") as db_f:
        print_filesystem(fs_dir, out_f=db_f)

def compare_entries(fs_dir, fs_entry, db_entry):
    fs_fullpath, fs_relpath, fs_info = fs_entry
    db_relpath, db_info = db_entry

    db_fullpath = "{}/{}".format(fs_dir, db_relpath)

    if fs_fullpath != db_fullpath:
        log.error("DB/FS mismatch ... {} != {}".format(db_relpath, fs_relpath))
        
        return db_fullpath > fs_fullpath, None

    errors = {}
    
    for key, fs_val in fs_info.items():
        db_val = db_info[key]
        if db_val == fs_val:
            continue
    
        errors[key] = (db_val, fs_val)

    if errors:
        log.warning("{} on {}".format(db_relpath, ", ".join(errors.keys())))
    
    return None, errors

def compare_fs_db(fs_dir, db_file):
    total_len = db_length(db_file)
    
    count = 0
    db = browse_db(db_file)
    fs = browse_filesystem(fs_dir)
    ret = None

    try:
        new_f = open(NEW_FILES, "w+")
        missing_f = open(MISSING_FILES, "w+")
        different_f = open(DIFFERENT_FILES, "w+")
        good_f = open(GOOD_FILES, "w+")
        
        while True:
            if ret is None:
                fs_entry = next(fs)
                
                if fs_entry is not None:
                    # not a new directory
                    db_entry = next(db)
            
            elif ret: # is True
                fs_entry = next(fs)
            else: # ret is False
                db_entry = next(db)

            if fs_entry is None:
                # new directory
                continue 
            
            count += 1
            # returns None if could compare,
            #      or db_fullpath > fs_fullpath
            ret, diff = compare_entries(fs_dir, fs_entry, db_entry)
            
            fs_fullpath, fs_relpath, fs_info = fs_entry
            db_relpath, db_info = db_entry

            progress(count, total_len)
            
            if ret is None:
                if not diff:
                    # files are identical
                    print(db_relpath, file=good_f)
                else:
                    # there are some differences, in diff dict
                    print("{}: {}".format(db_relpath, ", ".join(diff.keys())),
                          file=different_f)
            else:
                # one of the files is missing
                if ret:
                    # on the database
                    print(fs_fullpath, file=new_f)
                else:
                    # on the filesystem
                    print(db_relpath, file=missing_f)
                
                
    except StopIteration:
        log.info("Done, {} files compared.".format(count))
        
    finally:
        if missing_f:
            missing_f.close()
        if different_f:
            different_f.close()
        if new_f:
            new_f.close()
            
class Done(Exception): pass
    
DEFAULT_DB_FILE = "db.txt"
DEFAULT_FS_DIR = "/var/webalbums"
NOP = False

if __name__ == '__main__':
    try:
        args = docopt(__doc__, version='backup.py 0.9')

        db_file = args["--db"]
        if not db_file:
            db_file = DEFAULT_DB_FILE

        fs_dir = args["--fs"]
        if not fs_dir:
            fs_dir = DEFAULT_FS_DIR
            
        if args["create"]:
            print("create database {} from {}".format(db_file, fs_dir))
            
            if NOP: raise Done()

            create_database(db_file, fs_dir)
        
        elif args["check"]:        
            if args["local"]:
                fs_file = "/var/webalbums"
            elif args["external"]:
                fs_file = "/media/sdf1/data.git"
            elif args["rsync"]:
                raise ValueError("rsync check not implemented yet.")
            else:
                fs_file = args["<path>"]
            
            print("check {} against {}".format(fs_file, db_file))
            
            if NOP: raise Done()

            for to_remove in STARTUP_CLEANING:
                try:
                    os.remove(to_remove)
                except OSError: pass
            
            compare_fs_db(fs_file, db_file)
            
        else:
            print(__doc__)
    except Done:
        assert NOP
        log.critical("Done")
    except Exception as e:
        log.critical(e)
        traceback.print_exc()
    finally:
        if NOP:
            print("---")
            print("  "+"\n  ".join("{:10s}->  {}".format(k, v) for k, v in args.items() if v))
            print("---")
            print("  "+"\n  ".join("{:10s}->  {}".format(k, v) for k, v in args.items() if not v))
