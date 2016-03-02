import os

import common, config, verify

import logging; log = logging.getLogger('backup.status')

def do_status(args):    
    fs_dir = os.path.abspath(".")

    do_checksum = args["--checksum"]
    
    repo = common.get_repo(fs_dir)
    if not repo:
        log.critical("Could not find a repository with {} in copies...".format(fs_dir))
        return

    def do_clean():
        for to_remove in config.STATUS_FILES:
            try:
                path = os.path.join(repo.tmp_dir, to_remove)
                os.remove(path)
            except OSError:
                pass
            
    if args["clean"]:
        do_clean()
        log.info("Status of repository '{}' cleaned.".format(repo.name))
    elif args["verify"]:
        verify.verify_all(repo, fs_dir) 
    else:
        do_clean()

        status(repo, fs_dir, do_checksum)
        
def status(repo, fs_dir, do_checksum):
    log.info("Getting status of {} ({}) against repository '{}'.".format(repo.copyname, fs_dir, repo.name))
             
    compare_fs_db(repo, fs_dir, do_checksum)

def is_missing_in_fs(fs_fullpath, db_fullpath):
    # files are first
    fs_depth = fs_fullpath.count("/")
    db_depth = db_fullpath.count("/")

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
        
        is_missing_in_fs(fs_fullpath, db_fullpath)
        
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

def compare_fs_db(repo, fs_dir, do_checksum):
    if not os.path.exists(fs_dir):
        log.critical("Path '{}' does not exist.".format(fs_dir))
        return
    
    total_len = common.db_length(repo.db_file)

    if not total_len:
        log.critical("Database is empty.")
        return
    
    count = 0
    db = common.browse_db(repo.db_file)
    fs = common.browse_filesystem(fs_dir, do_checksum)
    missing_on_fs = None

    try:
        new_f = open(repo.NEW_FILES, "w+")
        missing_f = open(repo.MISSING_FILES, "w+")
        different_f = open(repo.DIFFERENT_FILES, "w+")
        good_f = open(repo.GOOD_FILES, "w+")

        good, different, missing, new = 0, 0, 0, 0
        
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
                raise StopIteration()
            
            if fs_entry is False: # no more fs entries
                missing_on_fs = True # so db cannot be on fs
                db_relpath, db_info = db_entry
            elif db_entry is False: # no more db entries
                missing_on_fs = False # so fs cannot be on db
                fs_fullpath, fs_relpath, fs_info = fs_entry
            else:
                # returns None if could compare,
                #      or db_fullpath > fs_fullpath
                missing_on_fs, diff = compare_entries(fs_dir, fs_entry, db_entry, do_checksum)
            
                fs_fullpath, fs_relpath, fs_info = fs_entry
                db_relpath, db_info = db_entry
            
            common.progress(count, total_len)
            count += 1
            
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
                    log.info("missing: {} in {}".format(fs_relpath, repo.db_file))
                    assert os.system('/usr/bin/grep "{}" "{}" --quiet'.format(fs_relpath, repo.db_file)) != 0
                    
                    print(fs_relpath, file=new_f)
                    new += 1
                
                
    except StopIteration:
        common.progress(total_len, total_len)
        print("")
        
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


