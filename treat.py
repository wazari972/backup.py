#! /usr/bin/python3

import os, shutil
import tempfile
import logging
log = logging.getLogger('root')

import common

NOP = False

def do_treat(args):
    fs_dir = os.path.abspath(".")
    
    repo = common.get_repo(fs_dir)
    if not repo:
        log.critical("Could not find a repository with {} in copies...".format(fs_dir))
        return
    
    if args["new"] or args["all"]:
        treat_new(repo, fs_dir)

    if args["missing"] or args["all"]:
        treat_missing(repo, fs_dir)
    
    if args["updated"] or args["all"]:
        treat_updated(repo, fs_dir)

def treat_new(repo, fs_dir):
    with open(repo.NEW_FILES) as new_f:
        new_files = [f[:-1] for f in new_f.readlines()]

    tmpdir = tempfile.mkdtemp()
    
    new_dir = "{}/new_files".format(tmpdir)
    os.mkdir(new_dir)
    log.critical("New files in {}".format(new_dir))
    
    for new in list(new_files):
        filename = new.replace("/", "_")

        src = "{}/{}".format(origin, new)
        if not os.path.exists(src):
            log.warn("File {} doesn't exist anymore, is the database up-to-date?".format(src))
            new_files.remove(new)
            continue
        
        os.symlink(src, "{}/{}".format(new_dir, filename))

    if not new_files:
        log.warn("No new files.")
        return

    os.system("nemo {}".format(new_dir))
    
    try:
        log.warn("Delete unwanted files in {}".format(new_dir)
                 + " and press Enter to continue or ^C^C to exit.")
        input()
    except KeyboardInterrupt:
        print("")
        log.warn("^C caught, do again to exit.")
        try:
            input()
        except KeyboardInterrupt:
            print("")
            log.warn("Second ^c caught, exiting.")
            return
        
    for new in new_files:
        filename = new.replace("/", "_")

        def save_file():
            log.critical("Copy {} from {} to {}.".format(new, origin, local))
            
            if NOP: return
        
            src = "{}/{}".format(origin, new)
            dst = "{}/{}".format(local, new)

            dst_dir = dst.rpartition("/")[0]
        
            try: os.mkdir(dst_dir)
            except FileExistsError: pass # ignore
        
            shutil.copy(src, dst)

        def delete_file():
            log.critical("Delete {} from {}.".format(new, origin))
            
            if NOP: return
            
            src = "{}/{}".format(origin, new)
            src_dir = src.rpartition("/")[0]
            
            os.remove(src)
            
            try: os.rmdir(src_dir)
            except OSError: pass # ignore
                
        if os.path.exists("{}/{}".format(new_dir, filename)):
            save_file()
        else:
            delete_file()
        
    shutil.rmtree(tmpdir)

def treat_updated(repo, fs_dir):
    pass

def treat_missing(repo, fs_dir):
    pass
