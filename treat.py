#! /usr/bin/python3

import os, shutil
import tempfile
import logging
from collections import OrderedDict

log = logging.getLogger('backup.treat')

import common, status, config

def do_treat(args):
    fs_dir = os.path.abspath(".")
    
    repo = common.get_repo(fs_dir)
    if not repo:
        log.critical("Could not find a repository with {} in copies...".format(fs_dir))
        return

    if not status.has_status(repo):
        log.critical("Status files are missing, run `status` first.")
        return
    
    if args["new"] or args["all"]:
        treat_new(repo, fs_dir, delete_on_missing=args["--delete"])

    if args["missing"] or args["all"]:
        treat_missing(repo, fs_dir)
    
    if args["updated"] or args["all"]:
        treat_updated(repo, fs_dir)

    if args["moved"] or args["all"]:
        treat_moved(repo, fs_dir)
        
    log.warn("Don't forget to run `status --force` to refresh status files.")
    
def treat_new(repo, fs_dir, delete_on_missing=False):
    treat_generic(repo, fs_dir, config.NEW_FILES, delete_on_missing)

def treat_updated(repo, fs_dir):
    treat_generic(repo, fs_dir, config.DIFFERENT_FILES)

def treat_moved(repo, fs_dir):
    treat_generic(repo, fs_dir, config.MOVED_FILES)
    return

def treat_missing(repo, fs_dir):
    if repo.get_copies()["master"] == fs_dir:
        log.critical("Current directory is master repository, nothing to do with missing files :(.")
        return
    
    treat_generic(repo, fs_dir, config.MISSING_FILES)
    
def treat_generic(repo, fs_dir, status_file, delete_on_missing=False):
    origin = repo.get_copies()["master"]
    do_difference = status_file == config.DIFFERENT_FILES
    status_descr = config.STATUS_FILES_DESC[status_file]
    
    status_filename = repo.get_status_fname(status_file)
    with open(status_filename) as status_f:
        status_files = OrderedDict()
        for line in status_f.readlines():
            fname, _, info_str = line[:-1].partition(" -> ")
            
            status_files[fname] = OrderedDict(item.split(": ") for item in info_str.split(", "))
    
    tmpdir = tempfile.mkdtemp()
    
    status_dir = os.path.join(tmpdir, status_descr.lower().replace(" ", "_"))
    os.mkdir(status_dir)

    def get_filename_for_diff(filename, from_path):
        if origin == fs_dir:
            return filename
        
        fname, _, ext = filename.rpartition(".")
        return ".".join((fname, "local" if from_path == fs_dir else "origin", ext))

    has_incorrect = False
    for status in list(status_files):
        def symlink(from_path):
            src = os.path.join(from_path, status)

            filename = status.replace(os.path.sep, "_")
            if do_difference:
                filename = get_filename_for_diff(filename, from_path)
            
            log.info("{} in <{}> {}".format(status_descr, repo.copyname, status))
            os.symlink(src, os.path.join(status_dir, filename))

        correct = True
        
        def is_consistent(local_should_exist, origin_should_exist, filename=status):
            def _is_consistent(at_origin, should_exist):
                location_name = "master" if at_origin else "local"
                file_location = origin if at_origin else fs_dir
                file_to_test = os.path.join(file_location, filename)

                file_exists = os.path.exists(file_to_test)
            
                if should_exist and not file_exists:
                    log.error("{}: file '{}' doesn't exist in {} directory '{}'".format(status_descr, filename, location_name, file_location))
                    return False
                if not should_exist and file_exists:
                    log.error("{}: file '{}' exists in {} directory '{}'".format(status_descr, filename, location_name, file_location))
                    return False
                return True

            return (_is_consistent(at_origin=False, should_exist=local_should_exist) and 
                    _is_consistent(at_origin=True, should_exist=origin_should_exist))
        
        if status_file == config.MISSING_FILES:
            correct = is_consistent(local_should_exist=False, origin_should_exist=True)
                
        elif status_file == config.NEW_FILES:
            correct = is_consistent(local_should_exist=True, origin_should_exist=False)
                
        elif status_file == config.DIFFERENT_FILES:
            correct = is_consistent(local_should_exist=True, origin_should_exist=True)
                            
        elif status_file == config.MOVED_FILES:
            moved_from = status_files[status]["moved_from"]

            correct = (is_consistent(local_should_exist=True, origin_should_exist=False) and
                       is_consistent(local_should_exist=False, origin_should_exist=True, filename=moved_from))
        else:
            assert False # should not come here
            
        if not correct:
            has_incorrect = True
            del status_files[status]
            continue
                
        symlink(origin)
        
        if do_difference and not origin == fs_dir:
            symlink(fs_dir)

    if has_incorrect:
        log.warn("Is the database up-to-date?")
        
    if not status_files:
        log.error("No {}{}.".format(status_descr.lower(), " remaining" if has_incorrect else ""))
        shutil.rmtree(tmpdir)
        return

    try:
        FILE_BROWSER = "nemo"
            
        log.warn("{} listed in {}.".format(status_descr, status_dir))
        if fs_dir == origin:
            log.info("Current directory is master repository, you can only review what happend.")
        else:
            log.info("Delete files that should not be treated.")
        log.error("Press Enter to start '{}', ".format(FILE_BROWSER)
                  +"'s' or ^C to skip file browsing, or 'q' to quit.")
        inp = input()
        if inp.startswith("q"):
            log.error("Quit request, bye")
            shutil.rmtree(tmpdir)
            return
        elif not inp.startswith("s"):
            log.info("Starting {} ...".format(FILE_BROWSER))
            os.system("{} '{}' &".format(FILE_BROWSER, status_dir))
    except KeyboardInterrupt:
        print("")
        log.warn("^C caught, skipping file browsing.")
        
    try:
        log.error("Press Enter to treat files or ^C to exit.")
        input()
    except KeyboardInterrupt:
        print("")
        log.warn("^C caught, exiting.")
        return

    if (fs_dir == origin and (do_difference or not delete_on_missing)):
        log.error("Current directory is master repository, nothing more to do ...")
        log.error("Consider running `update` instead, or `status ... --delete`.")
        return
    
    for status in status_files:
        filename = status.replace(os.path.sep, "_")

        def save_file(from_path, to_path):
            log.critical("Copy {} to {}.".format(os.path.join(origin, status), fs_dir))
        
            src = os.path.join(from_path, status)
            dst = os.path.join(to_path, status)

            dst_dir = dst.rpartition(os.path.sep)[0]

            if config.NOP: return
            
            try: os.mkdir(dst_dir)
            except FileExistsError: pass # ignore
        
            shutil.copy(src, dst)

        def delete_file():
            log.critical("Delete {} from {}.".format(status, origin))
            
            src = os.path.join(origin, status)
            src_dir = src.rpartition(os.path.sep)[0]

            if config.NOP: return
            os.remove(src)
            
            try: os.rmdir(src_dir)
            except OSError: pass # ignore
            
        if do_difference:
            local_symname = get_filename_for_diff(filename, fs_dir)
            origin_symname = get_filename_for_diff(filename, origin)

            has_local = os.path.exists(local_symname)
            has_origin = os.path.exists(origin_symname)

            if has_local and has_local: pass # ignore
            elif has_local: # keep local
                save_file(fs_dir, origin)
            else: # keep origin
                save_file(origin, fs_dir)
                
        elif os.path.exists(os.path.join(status_dir, filename)):
            save_file(origin, fs_dir)
        elif delete_on_missing:
            delete_file()
            
    shutil.rmtree(tmpdir)
