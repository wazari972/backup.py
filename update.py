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
    updated, new, missing, untouched, moved = 0, 0, 0, 0, 0

    tmp_db_file = "{}.tmp".format(repo.db_file)

    progress = status.progress_on_fs_and_db(repo, fs_dir, do_checksum)
    
    try:
        tmp_db_f = open(tmp_db_file, "w+")

        while True:
            state, diff, db_entry, fs_entry = next(progress)
            
            fs_fullpath, fs_relpath, fs_info = fs_entry
            db_relpath, db_info = db_entry
            
            entry_to_save = fs_entry
            
            if state is status.FileState.OK:
                untouched += 1
                entry_to_save = db_entry
                
            elif state is status.FileState.DIFFERENT:
                assert diff
                updated += 1
                if not do_checksum:
                    # force compute the checksum if disabled
                    fs_info["md5sum"] = common.checksum(fs_fullpath)
                    
            elif state is status.FileState.MISSING_IN_FS:
                new += 1
                continue # skip this entry
            
            elif state is status.FileState.MISSING_ON_DB:
                missing += 1
                if not do_checksum:
                    # force compute the checksum if disabled
                    fs_info["md5sum"] = common.checksum(fs_fullpath)
                    
            elif state is status.FileState.MOVED:
                assert False
            else:
                assert False # should not come here
                
            common.print_a_file(entry_to_save, tmp_db_f)
            
    except StopIteration:
        print("")

        log.critical("Database updated.")
        log.error("{} entries untouched".format(untouched))
        log.error("{} entries added".format(missing))
        log.error("{} entries updated".format(updated))
        log.error("{} entries removed".format(new))
        log.error("{} entries moved".format(moved))
        
        tmp_db_f.close()
        tmp_db_f = None # don't close it twice
        
        try: os.remove(repo.db_file)
        except OSError: pass

        os.rename(tmp_db_file, repo.db_file)

        status.do_clean(repo)
        
    finally:
        if tmp_db_f:
            tmp_db_f.close()
