#! /usr/bin/python3
import os
import logging
import config

log = logging.getLogger('backup.verify')


database = set()

def prepare_database(repo):
    global database
    with open(repo.db_file) as db_f:
        for line in db_f.readlines():
            database.add(line.partition(" -> ")[0])
    
def in_database(relpath):
    assert database
    
    return relpath in database

def in_filesystem(origin, relpath):
    path = (relpath if relpath.startswith(origin)
            else "{}/{}".format(origin, relpath))
    return os.path.exists(path)


def verify_new(repo, origin):
    prepare_database(repo)

    correct = True
    with open(repo.NEW_FILES) as new_f:
        for line in new_f.readlines():
            fname = line.partition(" -> ")[0]

            if in_database(fname):
                log.warn("NEW: {} found in database".format(fname))
                correct = False
            if not in_filesystem(origin, fname):
                log.warn("NEW: {} not in filesystem".format(fname))
                correct = False
    return correct

def verify_missing(repo, origin):
    prepare_database(repo)

    correct = True
    with open(repo.MISSING_FILES) as missing_f:
        for line in missing_f.readlines():
            fname = line.partition(" -> ")[0]

            if not in_database(fname):
                log.warn("MISSING: {} not in database".format(fname))
                correct = False
            if in_filesystem(origin, fname):
                log.warn("MISSING: {} in filesystem".format(fname))
                correct = False
    return correct

def verify_different_good(repo, origin, do_good=False):
    prepare_database(repo)
    correct = True
    
    def verif(what, line):
        global correct
        
        if not in_database(fname):
            log.warn("{}: {} not in database".format(what, fname))
            correct = False
        if not in_filesystem(origin, fname):
            log.warn("{}: {} not in filesystem".format(what, fname))
            correct = False
            
    
    with open(repo.DIFFERENT_FILES) as different_f:
        for line in different_f.readlines():
            fname = line.partition(" -> ")[0]
            verif("DIFF", line)
            
    if not do_good:
        return correct

    with open(repo.GOOD_FILES) as good_f:
        for line in good_f.readlines():
            fname = line.partition(" -> ")[0]

            verif("GOOD", line)
            
    return correct

def verify_moved(repo, origin):
    log.critical("Moved files:                 Not implemented")
    return False
    
def verify_all(repo, fs_dir):
    log.warn("Verify  {} against {}".format(fs_dir, repo.db_file))
              
    prepare_database(repo)

    try:
        if verify_new(repo, fs_dir):
            log.info("New files:                   Everythin OK :)")
    except Exception as e:
        log.error("Could not verify new files: {}".format(e))

    try:
        if verify_missing(repo, fs_dir):
            log.info("Missing files:               Everythin OK :)")
    except Exception as e:
        log.error("Could not verify missing files: {}".format(e))
        
    try:
        if verify_moved(repo, fs_dir):
            log.info("Moved files:                 Everythin OK :)")
    except Exception as e:
        log.error("Could not verify moved files: {}".format(e))
        
    try:
        if verify_different_good(repo, fs_dir, do_good=True):
            log.info("Different and good files:    Everythin OK :)")
    except Exception as e:
        log.error("Could not different/good files: {}".format(e))

