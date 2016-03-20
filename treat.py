#! /usr/bin/python3

import os, shutil
import tempfile
import logging
log = logging.getLogger('backup.treat')

import common, status

NOP = False

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

    log.warn("Don't forget to run `status --force` to refresh status files.")
    
def treat_new(repo, fs_dir, delete_on_missing=False):
    treat_generic(repo.get_copies()["master"], fs_dir,
                  "New files", repo.NEW_FILES, "new_files",
                  delete_on_missing)

def treat_updated(repo, fs_dir):
        treat_generic(repo.get_copies()["master"], fs_dir,
                      "Different files", repo.DIFFERENT_FILES, "different_files",
                      do_difference=True)

def treat_missing(repo, fs_dir):
    if repo.get_copies()["master"] == fs_dir:
        log.critical("Current directory is master repository, nothing to do with missing files :(.")
        return
    
    treat_generic(repo.get_copies()["master"], fs_dir,
                  "Missing files", repo.MISSING_FILES, "missing_files")
    
def treat_generic(origin, local, name, status_file, dirname,
                  delete_on_missing=False, do_difference=False):
    
    with open(status_file) as status_f:
        status_files = [f[:-1].partition("#")[0].strip() for f in status_f.readlines()]

    tmpdir = tempfile.mkdtemp()
    
    status_dir = "{}/{}".format(tmpdir, dirname)
    os.mkdir(status_dir)

    def get_filename_for_diff(filename, from_path):
        if origin == local:
            return filename
        
        fname, _, ext = filename.rpartition(".")
        return"{}.{}.{}".format(fname,
                                "local" if from_path is local else "origin",
                                ext)
    
    for status in list(status_files):
        def symlink(from_path):
            src = "{}/{}".format(from_path, status)
            
            if not os.path.exists(src):
                log.warn("File {} doesn't exist anymore; is the database up-to-date?".format(src))
                status_files.remove(status)
                return False

            filename = status.replace("/", "_")
            if do_difference:
                filename = get_filename_for_diff(filename, from_path)
            
            log.info("{}: {}".format(name, src))
            os.symlink(src, "{}/{}".format(status_dir, filename))

            return True
        
        if not symlink(origin):
            continue

        if do_difference and not origin == local:
            if not symlink(local):
                continue
        
    if not status_files:
        shutil.rmtree(tmpdir)
        log.warn("No {}.".format(name.lower()))
        return

    log.error("{} in {}".format(name, status_dir))
    os.system("nemo {} &".format(status_dir))

    try:
        if local == origin:
            log.warn("Current directory is master repository, you can only review what happend")
        else:
            log.warn("Delete unwanted files in {}".format(status_dir)
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

    if (local == origin and
        do_difference or not delete_on_missing):
            log.error("Current directory is master repository, nothing more to do ...")
            log.error("Consider running `update` instead, or `status ... --delete`.")
            return
    
    for status in status_files:
        filename = status.replace("/", "_")

        def save_file(from_path, to_path):
            log.critical("Copy {}/{} to {}.".format(origin, status, local))
        
            src = "{}/{}".format(from_path, status)
            dst = "{}/{}".format(to_path, status)

            dst_dir = dst.rpartition("/")[0]

            if NOP: return
            try: os.mkdir(dst_dir)
            except FileExistsError: pass # ignore
        
            shutil.copy(src, dst)

        def delete_file():
            log.critical("Delete {} from {}.".format(status, origin))
            
            src = "{}/{}".format(origin, status)
            src_dir = src.rpartition("/")[0]

            if NOP: return
            os.remove(src)
            
            try: os.rmdir(src_dir)
            except OSError: pass # ignore
            
        if not do_difference:
            if os.path.exists("{}/{}".format(status_dir, filename)):
                save_file(origin, local)
            elif delete_on_missing:
                delete_file()
        else:
            local_symname = get_filename_for_diff(filename, local)
            origin_symname = get_filename_for_diff(filename, origin)

            has_local = os.path.exists(local_symname)
            has_origin = os.path.exists(origin_symname)

            if has_local and has_local:
                pass # ignore
            else:
                if has_local: # keep local
                    save_file(local, origin)
                else: # keep origin
                    save_file(origin, local)
                
            
    shutil.rmtree(tmpdir)
