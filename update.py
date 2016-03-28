import os

import common, status, config

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
    lists_of_files = status.compare_fs_db(repo, fs_dir, do_checksum, updating=True)
    
    new = lists_of_files[config.NEW_FILES]
    missing = lists_of_files[config.MISSING_FILES]
    good = lists_of_files[config.GOOD_FILES]
    different = lists_of_files[config.DIFFERENT_FILES]
    moved = lists_of_files[config.MOVED_FILES]

    # only skip MISSING
    to_save = list(good)
    to_update = list(different)

    if not do_checksum:
        # force checksum for database entry
        to_update += new
    else:
        to_save += new
    
    for fname, old_info in to_update:
        fs_fullpath = os.path.join(fs_dir, fname)
        info = common.get_file_info(fs_fullpath, do_checksum=True)

        to_save.append((fname, info))
                       
    for fname, info in moved:
        del info["moved_from"]
        to_save.append((fname, info))

    # sort to match DB order
    to_save = sorted(to_save, key=lambda entry: entry[0])
    
    tmp_db_file = "{}.tmp".format(repo.db_file)    
    with open(tmp_db_file, "w+") as tmp_db_f:
        for fname, info in to_save:
            common.print_a_file(fname, info, tmp_db_f)

    try: os.remove(repo.db_file)
    except OSError: pass

    os.rename(tmp_db_file, repo.db_file)
            
    log.warn("Database updated.")
    log.info("{} entries untouched".format(len(good)))
    log.info("{} entries added".format(len(missing)))
    log.info("{} entries updated".format(len(different)))
    log.info("{} entries removed".format(len(new)))
    log.info("{} entries moved".format(len(moved)))

    status.do_clean(repo)
