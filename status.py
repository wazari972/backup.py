import os, time

import common, config, verify
from enum import Enum
import logging; log = logging.getLogger('backup.status')
from collections import OrderedDict

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
    for fname, desc in config.STATUS_FILES_DESC.items():
        log.warn(desc)
        
        fpath = repo.get_status_fname(fname)
        
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
             
    compare_and_save_fs_db(repo, fs_dir, do_checksum)

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

def compare_fs_db(repo, fs_dir, do_checksum, updating=False):
    progress = progress_on_fs_and_db(repo, fs_dir, do_checksum)

    good, missing, new, different, moved = [], [], [], [], []
    
    try:
        while True:
            state, diff, db_entry, fs_entry = next(progress)

            try:
                fs_fullpath, fs_relpath, fs_info = fs_entry
            except Exception: pass
            
            try:
                db_relpath, db_info = db_entry
            except Exception: pass
            
            if state is FileState.OK:
                good.append((db_relpath, db_info))
                
            elif state is FileState.DIFFERENT:
                assert diff

                different.append((db_relpath, diff))
                
            elif state is FileState.MISSING_IN_FS:
                if not updating:
                    assert not os.path.exists("{}/{}".format(fs_dir, db_relpath))
                
                missing.append((db_relpath, db_info))
                
            elif state is FileState.MISSING_ON_DB:
                if not updating:
                    command = '/usr/bin/grep "{}" "{}" --quiet'.format(fs_relpath, repo.db_file)
                    assert os.system(command) # assert !0 (text not found)
                
                new.append((fs_relpath, fs_info))
                
            else: # MOVED should not happend here
                log.critical("Incorrect state: {}".format(state))
                assert False # should not come here
                
    except StopIteration:
        pass

    # compute moved files
    for new_file_info in list(new):
        new_file, new_info = new_file_info
        
        if not do_checksum: # if checksum not computed before
            fs_fullpath = os.path.join(fs_dir, new_file)
            new_info = common.get_file_info(fs_fullpath, do_checksum=True)

        missing_file_info = [(i, missing_file_info[0]) for i, missing_file_info in enumerate(missing)
                      if missing_file_info[1]["md5sum"] == new_info["md5sum"]]

        if not missing_file_info:
            continue

        assert len(missing_file_info) == 1
        idx, missing_file = missing_file_info[0]

        info = new_info.copy()
        info["moved_from"] = missing_file
        moved.append((new_file, info))
        log.warning("{} # actually moved from {}".format(new_file, missing_file))

        missing.pop(idx)
        new.remove(new_file_info)
        
    return OrderedDict((
            (config.GOOD_FILES, good),
            (config.NEW_FILES, new),
            (config.MISSING_FILES, missing),
            (config.DIFFERENT_FILES, different),
            (config.MOVED_FILES, moved),
            ))
    
def compare_and_save_fs_db(repo, fs_dir, do_checksum):
    if not os.path.exists(fs_dir):
        log.critical("Path '{}' does not exist.".format(fs_dir))
        return

    if not common.db_length(repo.db_file):
        log.critical("Database is empty.")
        return
    
    status_files = {fname: open(repo.get_status_fname(fname), "w+")
                    for fname, descr in config.STATUS_FILES_DESC.items()}

    lists_of_files = compare_fs_db(repo, fs_dir, do_checksum)
        
    log.warn("Done, {} files compared.".format(sum(map(len, lists_of_files.values()))))

    for fname, flist in lists_of_files.items():
        log.info("{}: {}".format(config.STATUS_FILES_DESC[fname], len(flist)))
        status_f = status_files[fname]

        for entry in flist:
            relpath, info = entry
                
            
            common.print_a_file(relpath, info, status_f)
        
    for status_file in status_files.values():
        status_file.close()
