import os, time

import common, config, verify
from enum import Enum
import logging; log = logging.getLogger('backup.status')

def do_status(args):    
    fs_dir = os.path.abspath(".")

    do_checksum = args["--checksum"]
    
    repo = common.get_repo(fs_dir)
    if not repo:
        log.critical("Could not find a repository with {} in copies...".format(fs_dir))
        return
        
    if args["show"]:
        do_show(repo)
        
    elif args["clean"]:
        if not do_clean(repo):
            log.warn("No status file to clean for repository '{}'.".format(repo.name))
        
    elif args["verify"]:
        verify.verify_all(repo, fs_dir)
        
    else:
        if has_status(repo) and not args["--force"]:
            do_show(repo)
            log.info("(Run `status --force` to force rescan.)")
        else:
            do_clean(repo)
            status(repo, fs_dir, do_checksum)

def do_clean(repo):
    cleaned = False
    for to_remove in config.STATUS_FILES:
        try:
            path = os.path.join(repo.tmp_dir, to_remove)
            os.remove(path)
            cleaned = True
        except OSError:
            pass
    if cleaned:
        log.info("Status of repository '{}' cleaned.".format(repo.name))
    return cleaned
            
def has_status(repo):
    for fname in config.STATUS_FILES:
        fpath = os.path.join(repo.tmp_dir, fname)
        
        if not os.path.exists(fpath):
            return False
    return True

def do_show(repo):
    min_ctime = None
    for fname, desc in config.STATUS_FILES_DESC:
        log.warn(desc)
        
        fpath = os.path.join(repo.tmp_dir, fname)
        
        fctime = os.path.getctime(fpath)
        min_ctime = min(min_ctime, fctime) if min_ctime is not None else fctime
        
        if not os.path.exists(fpath):
            log.warn("Doesn't exist.")
            continue
        
        with open(fpath) as fname_f:
            if fname is config.GOOD_FILES:
                log.info("{} entries".format(len(fname_f.readlines())))
            else:
                has = False
                for line in fname_f.readlines():
                    log.info(line[:-1])
                    has = True
                    
                if not has:
                    log.info("None")
    
    if min_ctime is not None:
        log.warn("  Status file created on: {}".format(time.ctime(min_ctime)))
    log.info("Database file created on: {}".format(time.ctime(os.path.getctime(repo.db_file))))
    
def status(repo, fs_dir, do_checksum):
    log.info("Getting status of {} ({}) against repository '{}'.".format(repo.copyname, fs_dir, repo.name))
             
    compare_fs_db(repo, fs_dir, do_checksum)

def is_missing_in_fs(fs_fullpath, db_fullpath):
    # files are first

    db_dir, _, db_name = db_fullpath.rpartition("/")
    fs_dir, _, fs_name = fs_fullpath.rpartition("/")
    
    missing_in_fs = (
        # not in the same directory ?
        db_dir < fs_dir if fs_dir != db_dir 
        else db_name < fs_name)

    return (FileState.MISSING_IN_FS if missing_in_fs
            else FileState.MISSING_ON_DB)
    

def compare_entries(fs_dir, fs_entry, db_entry, do_checksum):    
    fs_fullpath, fs_relpath, fs_info = fs_entry
    db_relpath, db_info = db_entry

    db_fullpath = "{}/{}".format(fs_dir, db_relpath)
    
    if fs_fullpath != db_fullpath:
        state = is_missing_in_fs(fs_fullpath, db_fullpath)
        
        if state is FileState.MISSING_IN_FS:
            log.warn("{} # missing in fs".format(db_relpath, fs_relpath))
        else:
            log.warn("{} # missing in db".format(fs_relpath, db_relpath))

        return state, None

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

    state = FileState.DIFFERENT if errors else FileState.OK
    
    if state is FileState.DIFFERENT:
        log.warning("{} # different {}".format(db_relpath, ", ".join(errors.keys())))
        
    return state, errors

class FileState(Enum):
    (OK,
     DIFFERENT,
     MISSING_ON_DB,
     MISSING_IN_FS,
     MOVED) = range(5)

def progress_on_fs_and_db(repo, fs_dir, do_checksum):
    total_len = common.db_length(repo.db_file)

    count = 0
    db = common.browse_db(repo.db_file)
    fs = common.browse_filesystem(fs_dir, do_checksum)
    state = FileState.OK

    while True:
        if state in (FileState.OK, FileState.DIFFERENT):
            fs_entry = next(fs)
                
            if fs_entry is not None:
                # not a new directory
                db_entry = next(db)

        elif fs_entry is False or state is FileState.MISSING_IN_FS:
            db_entry = next(db)
            
        elif db_entry is False or state is FileState.MISSING_ON_DB:
            fs_entry = next(fs)
            
        else:
            assert False # should not come here
                
        if fs_entry is None:
            # new directory
            continue 
            
        if fs_entry is False and db_entry is False:
            common.progress(total_len, total_len)
            print("")
            
            raise StopIteration()

        if fs_entry is False: # no more fs entries
            state = FileState.MISSING_IN_FS # so file cannot be on fs
            
        elif db_entry is False: # no more db entries
            state = FileState.MISSING_ON_DB # so file cannot be on db
            
        else:
            # returns None if could compare,
            #      or db_fullpath > fs_fullpath
            state, diff = compare_entries(fs_dir, fs_entry, db_entry, do_checksum)

        common.progress(count, total_len)
        count += 1

        yield state, diff, db_entry, fs_entry
        
def compare_fs_db(repo, fs_dir, do_checksum):
    if not os.path.exists(fs_dir):
        log.critical("Path '{}' does not exist.".format(fs_dir))
        return

    if not common.db_length(repo.db_file):
        log.critical("Database is empty.")
        return

    progress = progress_on_fs_and_db(repo, fs_dir, do_checksum)
    
    try:
        new_f = open(repo.NEW_FILES, "w+")
        missing_f = open(repo.MISSING_FILES, "w+")
        different_f = open(repo.DIFFERENT_FILES, "w+")
        good_f = open(repo.GOOD_FILES, "w+")
        moved_f = open(repo.MOVED_FILES, "w+")
        
        moved, good, different, missing, new = 0, 0, 0, 0, 0
        
        while True:
            state, diff, db_entry, fs_entry = next(progress)

            fs_fullpath, fs_relpath, fs_info = fs_entry
            db_relpath, db_info = db_entry
    
            if state is FileState.OK:
                print(db_relpath, file=good_f)
                good += 1
                
            elif state is FileState.DIFFERENT:
                assert diff

                print("{} # {}".format(db_relpath, ", ".join(diff.keys())),
                      file=different_f)
                different += 1
                
            elif state is FileState.MISSING_IN_FS:
                assert not os.path.exists("{}/{}".format(fs_dir, db_relpath))
                
                print(db_relpath, file=missing_f)
                missing += 1
                
            elif state is FileState.MISSING_ON_DB:
                command = '/usr/bin/grep "{}" "{}" --quiet'.format(fs_relpath, repo.db_file)
                
                assert os.system(command) # assert !0 (text not found)

                print(fs_relpath, file=new_f)
                new += 1
                
            elif state is FileState.MOVED:
                assert False
                moved += 1
            else:
                log.critical("Incorrect state: {}".format(state))
                assert False # should not come here
                
    except StopIteration:
        count = sum([good, different, missing, new, moved])
        
        log.warn("Done, {} files compared.".format(count))
        log.info("Good files: {}".format(good))
        log.info("Missing files: {}".format(missing))
        log.info("Different files: {}".format(different))
        log.info("New files: {}".format(new))
        log.info("Moved files: {}".format(moved))
        
    finally:
        for a_file in (missing_f, missing_f, different_f, new_f, good_f):
            try:
                a_file.close()
            except NameError: # variable doesn't exist
                pass
