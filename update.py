import os

import common, status

import logging; log = logging.getLogger('backup.update')

def do_update(args):
    fs_dir = os.path.abspath(".")

    repo = common.get_repo(fs_dir)

    if not repo:
        log.critical("Could not find a repository with {} in copies...".format(fs_dir))
        return

    do_checksum = args["--checksum"]
    
    update_database(repo, fs_dir, do_checksum)
    
def update_database(repo, fs_dir, do_checksum):
    total_len = common.db_length(repo.db_file)
    
    count = 0
    db = common.browse_db(repo.db_file)
    fs = common.browse_filesystem(fs_dir, do_checksum)
    missing_on_fs = None
    updated, new, missing, untouched = 0, 0, 0, 0

    tmp_db_file = "{}.tmp".format(repo.db_file)
    
    try:
        tmp_db_f = open(tmp_db_file, "w+")

        while True:
            if missing_on_fs is None:
                fs_entry = next(fs)
                
                if fs_entry is not None:
                    # not a new directory
                    db_entry = next(db)
            
            elif db_entry is False or missing_on_fs is True:
                fs_entry = next(fs)
            elif fs_entry is False or missing_on_fs is False:
                db_entry = next(db)
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
                missing_on_fs, diff = status.compare_entries(fs_dir, fs_entry, db_entry, do_checksum)
            
                fs_fullpath, fs_relpath, fs_info = fs_entry
                db_relpath, db_info = db_entry

            common.progress(count, total_len)
            count += 1

            a_file = fs_entry
            if missing_on_fs is None:
                if not diff:
                    # files are identical
                    untouched += 1
                    a_file = db_entry
                else:
                    # there are some differences, in diff dict
                    updated += 1
                    if not do_checksum:
                        # force compute the checksum if disabled
                        ds_entry["md5sum"] = common.checksum(fullpath)
            else:
                # the file is missing
                if missing_on_fs:
                    # on the database
                    new += 1
                    continue # skip this entry
                else:
                    # on the filesystem
                    missing += 1
                    
            common.print_a_file(a_file, tmp_db_f)
            
    except StopIteration:
        print("")

        log.critical("Database updated.")
        log.error("{} entries untouched".format(untouched))
        log.error("{} entries added".format(missing))
        log.error("{} entries updated".format(updated))
        log.error("{} entries removed".format(new))

        tmp_db_f.close()
        tmp_db_f = None # don't close it twice

        
        try: os.remove(repo.db_file)
        except OSError: pass

        os.rename(tmp_db_file, repo.db_file)
        
    finally:
        if tmp_db_f:
            tmp_db_f.close()
