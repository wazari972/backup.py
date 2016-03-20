import os

import common, status

import logging; log = logging.getLogger('backup.update')

def do_update(args):
    fs_dir = os.path.abspath(".")

    repo = common.get_repo(fs_dir)

    if not repo:
        log.critical("Could not find a repository with {} in copies...".format(fs_dir))
        return
    if not repo.copyname == "master":
        log.critical("Database can only be updated from master copy. "+
                     "Current directory is '{}' copy.".format(repo.copyname))
        return
    
    do_checksum = args["--checksum"]
    
    update_database(repo, fs_dir, do_checksum)
    
def update_database(repo, fs_dir, do_checksum):
    updated, new, missing, untouched = 0, 0, 0, 0

    tmp_db_file = "{}.tmp".format(repo.db_file)

    progress = status.progress_on_fs_and_db(repo, fs_dir, do_checksum)
    
    try:
        tmp_db_f = open(tmp_db_file, "w+")

        while True:
            missing_on_fs, diff, db_entry, fs_entry = next(progress)
            
            fs_fullpath, fs_relpath, fs_info = fs_entry
            db_relpath, db_info = db_entry
            
            entry_to_save = fs_entry
            
            if missing_on_fs is None:
                if not diff:
                    # files are identical
                    untouched += 1
                    entry_to_save = db_entry
                else:
                    # there are some differences, in diff dict
                    updated += 1
                    if not do_checksum:
                        # force compute the checksum if disabled
                        fs_info["md5sum"] = common.checksum(fs_fullpath)
            else:
                # the file is missing
                if missing_on_fs:
                    # on the database
                    new += 1
                    continue # skip this entry
                else:
                    # on the filesystem
                    missing += 1
                    if not do_checksum:
                        # force compute the checksum if disabled
                        fs_info["md5sum"] = common.checksum(fs_fullpath)
            
            common.print_a_file(entry_to_save, tmp_db_f)
            
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

        status.do_clean(repo)
        
    finally:
        if tmp_db_f:
            tmp_db_f.close()
