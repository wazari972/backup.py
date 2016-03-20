import os, time

import common, config, verify

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
    
    if fs_dir != db_dir:
        # not in the same directory
        return db_dir < fs_dir
    
    return db_name < fs_name

def compare_entries(fs_dir, fs_entry, db_entry, do_checksum):    
    fs_fullpath, fs_relpath, fs_info = fs_entry
    db_relpath, db_info = db_entry

    db_fullpath = "{}/{}".format(fs_dir, db_relpath)

    if fs_fullpath != db_fullpath:
        missing_on_fs = is_missing_in_fs(fs_fullpath, db_fullpath)
        
        if missing_on_fs:
            log.warn("{} # missing in fs".format(db_relpath, fs_relpath))
        else:
            log.warn("{} # missing in db".format(fs_relpath, db_relpath))
        
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

def progress_on_fs_and_db(repo, fs_dir, do_checksum):
    total_len = common.db_length(repo.db_file)

    count = 0
    db = common.browse_db(repo.db_file)
    fs = common.browse_filesystem(fs_dir, do_checksum)
    missing_on_fs = None

    while True:
        if missing_on_fs is None:
            fs_entry = next(fs)
                
            if fs_entry is not None:
                # not a new directory
                db_entry = next(db)
            
        elif fs_entry is False or missing_on_fs is True:
            # missing in DB, new in FS
            db_entry = next(db)
            
        elif db_entry is False or missing_on_fs is False:
            # missing in FS
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
            missing_on_fs = True # so db cannot be on fs
            
        elif db_entry is False: # no more db entries
            missing_on_fs = False # so fs cannot be on db
            
        else:
            # returns None if could compare,
            #      or db_fullpath > fs_fullpath
            missing_on_fs, diff = compare_entries(fs_dir, fs_entry, db_entry, do_checksum)

        common.progress(count, total_len)
        count += 1

        yield missing_on_fs, diff, db_entry, fs_entry
        
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

        good, different, missing, new = 0, 0, 0, 0
        
        while True:
            missing_on_fs, diff, db_entry, fs_entry = next(progress)

            try:
                fs_fullpath, fs_relpath, fs_info = fs_entry
                db_relpath, db_info = db_entry
            except:
                import pdb;pdb.set_trace()
            if missing_on_fs is None:
                if not diff:
                    # files are identical
                    print(db_relpath, file=good_f)
                    good += 1
                else:
                    # there are some differences, in diff dict
                    print("{} # {}".format(db_relpath, ", ".join(diff.keys())),
                          file=different_f)
                    different += 1
            else:
                # one of the files is missing
                if missing_on_fs:
                    # missing on the filesystem
                    assert not os.path.exists("{}/{}".format(fs_dir, db_relpath))

                    print(db_relpath, file=missing_f)
                    missing += 1
                else:
                    # missing on the database
                    #log.info("missing: {} in {}".format(fs_relpath, repo.db_file))
                    command = '/usr/bin/grep "{}" "{}" --quiet'
                    assert os.system(command.format(fs_relpath, repo.db_file)) != 0
                    
                    print(fs_relpath, file=new_f)
                    new += 1
                
    except StopIteration:
        count = sum([good, different, missing, new])
        
        log.warn("Done, {} files compared.".format(count))
        log.info("Good files: {}".format(good))
        log.info("Missing files: {}".format(missing))
        log.info("Different files: {}".format(different))
        log.info("New files: {}".format(new))
        
    finally:
        if missing_f:
            missing_f.close()
        if different_f:
            different_f.close()
        if new_f:
            new_f.close()


