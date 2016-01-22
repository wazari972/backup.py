#! /usr/bin/python3
import os
import logging
log = logging.getLogger('root')

import backup

database = set()

def prepare_database(db_file):
    global database
    with open(db_file) as db_f:
        for line in db_f.readlines():
            database.add(line.partition(" -> ")[0])
    
def in_database(relpath):
    assert database
    
    return relpath in database

def in_filesystem(origin, relpath):
    return os.path.exists("{}/{}".format(origin, relpath))


def verify_new(db_file, origin):
    prepare_database(db_file)
    
    correct = True
    with open(backup.NEW_FILES) as new_f:
        for line in new_f.readlines():
            fname = line[:-1]

            if in_database(fname):
                log.warn("NEW: {} in database".format(fname))
                correct = False
            if not in_filesystem(origin, fname):
                log.warn("NEW: {} not in filesystem".format(fname))
                correct = False
    return correct

def verify_missing(db_file, origin):
    prepare_database(db_file)
    
    correct = True
    with open(backup.MISSING_FILES) as new_f:
        for line in new_f.readlines():
            fname = line[:-1]

            if not in_database(fname):
                log.warn("MISSING: {} not in database".format(fname))
                correct = False
            if not in_filesystem("", fname):
                log.warn("MISSING: {} in filesystem".format(fname))
                correct = False
    return correct
