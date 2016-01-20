#! /usr/bin/python3

"""Backup tool

Usage:
  backup.py create [--db=<db.txt>] [--fs=<local>]
  backup.py update [--db=<db.txt>] [--fs=<local>]
  backup.py check (local | external | rsync | <path>) [--db=<db.txt>] [--checksum]
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
    LOG_LEVEL = logging.INFO
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
    print("\r%.2f%%" % (current/total*100), end="")
        
def checksum(fname):
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

def browse_filesystem(fs_dir, do_checksum):
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
                "md5sum" : checksum(fullpath) if do_checksum else "",
                "size" : str(st.st_size)
                }

            yield fullpath, relpath, info
        yield None

def print_filesystem(fs_dir, out_f=sys.stdout, do_checksum=True):
    for a_file in browse_filesystem(fs_dir, do_checksum):
        if a_file is None:
            if out_f == sys.stdout:
                print("---")
            continue
        
        print_a_file(a_file, out_f)

def print_a_file(a_file, out_f):
    relpath, info = a_file[-2:]
    print("{} -> {}".format(relpath,
                            ", ".join([ "{}: {}".format(k, v) for k,v in info.items()])),
          file=out_f)


def create_database(db_file, fs_dir):
    if os.path.exists(db_file):
        log.critical("Database file '{}' already exists. Delete it first to (re)create the database.".format(db_file))
        return
    
    with open(db_file, "w+") as db_f:
        print_filesystem(fs_dir, out_f=db_f)

def compare_entries(fs_dir, fs_entry, db_entry, do_checksum):
    fs_fullpath, fs_relpath, fs_info = fs_entry
    db_relpath, db_info = db_entry

    db_fullpath = "{}/{}".format(fs_dir, db_relpath)

    if fs_fullpath != db_fullpath:
        missing_on_fs = db_fullpath > fs_fullpath
            
        log.warn("{} # {}".format(fs_relpath, "missing" if missing_on_fs else "new"))
        
        return missing_on_fs, None

    errors = {}
    
    for key, fs_val in fs_info.items():
        if key == "md5sum" and not do_checksum:
            # ignore checksum
            continue
        
        db_val = db_info[key]
        
        if db_val == fs_val:
            # value is correct
            continue
    
        errors[key] = (db_val, fs_val)

    if errors:
        log.warning("{} # different {}".format(db_relpath, ", ".join(errors.keys())))
    
    return None, errors

def compare_fs_db(fs_dir, db_file, do_checksum):
    if not os.path.exists(fs_dir):
        log.critical("Path '{}' does not exist.".format(fs_dir))
        return
    
    total_len = db_length(db_file)
    
    count = 0
    db = browse_db(db_file)
    fs = browse_filesystem(fs_dir, do_checksum)
    ret = None

    try:
        new_f = open(NEW_FILES, "w+")
        missing_f = open(MISSING_FILES, "w+")
        different_f = open(DIFFERENT_FILES, "w+")
        good_f = open(GOOD_FILES, "w+")

        good, different, missing, new = 0, 0, 0, 0
        
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
            
            
            # returns None if could compare,
            #      or db_fullpath > fs_fullpath
            ret, diff = compare_entries(fs_dir, fs_entry, db_entry, do_checksum)
            
            fs_fullpath, fs_relpath, fs_info = fs_entry
            db_relpath, db_info = db_entry

            progress(count, total_len)
            count += 1
            
            if ret is None:
                if not diff:
                    # files are identical
                    print(db_relpath, file=good_f)
                    good += 1
                else:
                    # there are some differences, in diff dict
                    print("{}: {}".format(db_relpath, ", ".join(diff.keys())),
                          file=different_f)
                    different += 1
            else:
                # one of the files is missing
                if ret:
                    # on the database
                    print(fs_fullpath, file=new_f)
                    new += 1
                else:
                    # on the filesystem
                    print(db_relpath, file=missing_f)
                    missing += 1
                
                
    except StopIteration:
        print("")
        
        log.critical("Done, {} files compared.".format(count))
        log.error("Good files: {}".format(good))
        log.error("Missing files: {}".format(missing))
        log.error("Different files: {}".format(different))
        log.error("New files: {}".format(new))
        
    finally:
        if missing_f:
            missing_f.close()
        if different_f:
            different_f.close()
        if new_f:
            new_f.close()


def update_database(db_file, fs_dir, do_checksum):
    total_len = db_length(db_file)
    
    count = 0
    db = browse_db(db_file)
    fs = browse_filesystem(fs_dir, do_checksum)
    ret = None
    updated, new, missing, untouched = 0, 0, 0, 0

    tmp_db_file = "{}.tmp".format(db_file)
    
    try:
        tmp_db_f = open(tmp_db_file, "w+")
        
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
            
            
            # returns None if could compare,
            #      or db_fullpath > fs_fullpath
            ret, diff = compare_entries(fs_dir, fs_entry, db_entry, do_checksum)
            
            fs_fullpath, fs_relpath, fs_info = fs_entry
            db_relpath, db_info = db_entry

            progress(count, total_len)
            count += 1

            a_file = fs_entry
            if ret is None:
                if not diff:
                    # files are identical
                    untouched += 1
                    a_file = db_entry
                else:
                    # there are some differences, in diff dict
                    updated += 1
                    if not do_checksum:
                        # force compute the checksum if disabled
                        ds_entry["md5sum"] = checksum(fullpath)
            else:
                # the file is missing
                if ret:
                    # on the database
                    new += 1
                else:
                    # on the filesystem
                    missing += 1
                    continue # skip this entry
                
            print_a_file(a_file, tmp_db_f)
            
    except StopIteration:
        print("")

        log.critical("Database updated.")
        log.error("{} entries untouched".format(untouched))
        log.error("{} entries removed".format(missing))
        log.error("{} entries updated".format(updated))
        log.error("{} entries added".format(new))

        tmp_db_f.close()
        tmp_db_f = None # don't close it twice

        
        #try: os.remove(db_file)
        #except OSError: pass

        #os.rename(tmp_db_file, db_file)
        
    finally:
        if tmp_db_f:
            tmp_db_f.close()
            
class Done(Exception): pass
    
DEFAULT_DB_FILE = "db.txt"
DEFAULT_FS_DIR = "/var/webalbums"
NOP = False

def main(args):
    try:
        db_file = args["--db"]
        if not db_file:
            db_file = DEFAULT_DB_FILE

        fs_dir = args["--fs"]
        if not fs_dir:
            fs_dir = DEFAULT_FS_DIR

        do_checksum = args["--checksum"]
            
        #################
            
        if args["create"]:
            print("Create database {} from {}".format(db_file, fs_dir))
            
            if NOP: raise Done()

            create_database(db_file, fs_dir)
            
        elif args["update"]:
            print("Update database {} from {}".format(db_file, fs_dir))
            
            if NOP: raise Done()

            update_database(db_file, fs_dir, do_checksum)
            
        elif args["check"]:        
            if args["local"]:
                fs_file = "/var/webalbums"
            elif args["external"]:
                fs_file = "/media/sdf1/data.git"
            elif args["rsync"]:
                raise ValueError("rsync check not implemented yet.")
            else:
                fs_file = args["<path>"]
            
            print("Check {} against {} ({})".format(fs_file, db_file,
                                                    "checksum" if do_checksum else "fast"))
            
            if NOP: raise Done()

            for to_remove in STARTUP_CLEANING:
                try:
                    os.remove(to_remove)
                except OSError: pass
            
            compare_fs_db(fs_file, db_file, do_checksum)
            
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
            
if __name__ == '__main__':
    main(docopt(__doc__, version='backup.py 0.9'))
