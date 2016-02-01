import os
import yaml

import config
import common

import logging; log = logging.getLogger('backup.init')

def do_init(args):
    if not args["from"]:
        init_repository(args["<name>"], args["--force"])
    else:
        init_from_repository(args["<name>"], args["<backup-name>"], args["--force"])


def init_repository(name, force=False):
    fs_dir = os.path.abspath(".")

    repo = common.Repository(name)
    
    ###
    # create config dir
    ###
    
    try: os.mkdir(repo.cfg_dir)
    except FileExistsError: pass # ignore


    # check first if the database exists
    
    if not force and os.path.exists(repo.db_file):
        log.critical("Database file '{}' already exists. ".format(repo.db_file))
        log.warn("Delete it first to (re)create the database.")
        return
    
    ###
    # create copies file
    ###

    if os.path.exists(repo.copies_file):
        log.warn("COPIES file ({}) already exists, updating it...".format(repo.copies_file))
    
    copies = repo.get_copies(allow_new=True)
    
    copies["master"] = fs_dir
    
    repo.write_copies(copies)
    
    repo.set_copyname("master")
    
    try: os.mkdir(repo.tmp_dir)
    except FileExistsError: pass # ignore
    
    ###
    # create database
    ###

    log.info("Initializing {} database into {}.".format(name, repo.db_file))

    if not config.NOP:
        try:
            with open(repo.db_file, "w+") as db_f:
                common.print_filesystem(fs_dir, out_f=db_f)
        except Exception as e:
            log.critical("Database generation failed: {}".format(e))
            os.remove(repo.db_file)
    else:
        log.critical("NOP: print_filesystem({}, {})".format(repo.fs_dir, repo.db_file))
        
    log.info("Database for {} correctly initialized.".format(name))
    
def init_from_repository(src, name, force=False):
    fs_dir = os.path.abspath(".")

    repo = common.Repository(src)

    if not os.path.exists(repo.cfg_dir):
        log.error("Config dir '{}' doesn't exists.".format(repo.cfg_dir))
        return

    if not os.path.exists(repo.db_file):
        log.error("Database file '{}' doesn't exists.".format(repo.db_file))
        return

    if not os.path.exists(repo.copies_file):
        log.error("Copies file '{}' doesn't exists.".format(repo.copies_file))
        return
    
    copies = repo.get_copies()
    if not copies:
        log.error("Couldn't parse copies file.")
        return

    try:
        copyname = copies[name]
        log.error("Entry {} -> {} already in copies file.".format(name, copyname)) # fails if not
        if not force: return
    except KeyError: pass

    
    for key, value in copies.items():
        if fs_dir == value:
            log.error("Local directory '{}' alreay in copies of '{}' ({}).".format(fs_dir, repo.name, key))
            if not force:
                return
            
    
    
    copies[name] = fs_dir

    repo.write_copies(copies)
    
    log.info("Directory '{}' added to {} copies list.".format(fs_dir, src))
