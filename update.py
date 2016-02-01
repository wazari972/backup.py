def update_database(db_file, fs_dir, do_checksum):
    total_len = db_length(db_file)
    
    count = 0
    db = browse_db(db_file)
    fs = browse_filesystem(fs_dir, do_checksum)
    missing_on_fs = None
    updated, new, missing, untouched = 0, 0, 0, 0

    tmp_db_file = "{}.tmp".format(db_file)
    
    try:
        tmp_db_f = open(tmp_db_file, "w+")
        
        while True:
            if missing_on_fs is None:
                fs_entry = next(fs)
                
                if fs_entry is not None:
                    # not a new directory
                    db_entry = next(db)
            
            elif missing_on_fs: # is True
                fs_entry = next(fs)
            else: # missing_on_fs is False
                db_entry = next(db)

            if fs_entry is None:
                # new directory
                continue 
            
            
            # missing_on_fsurns None if could compare,
            #      or db_fullpath > fs_fullpath
            missing_on_fs, diff = compare_entries(fs_dir, fs_entry, db_entry, do_checksum)
            
            fs_fullpath, fs_relpath, fs_info = fs_entry
            db_relpath, db_info = db_entry

            progress(count, total_len)
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
                        ds_entry["md5sum"] = checksum(fullpath)
            else:
                # the file is missing
                if missing_on_fs:
                    # on the database
                    new += 1
                else:
                    # on the filesystem
                    missing += 1
                    continue # skip this entry
                
            print_a_file(a_file, tmp_db_f)
            
    except StopIteration:
        print("")

        log.critical("Database updated.")
        log.error("{} entries untouched".format(untouched))
        log.error("{} entries removed".format(missing))
        log.error("{} entries updated".format(updated))
        log.error("{} entries added".format(new))

        tmp_db_f.close()
        tmp_db_f = None # don't close it twice

        
        #try: os.remove(db_file)
        #except OSError: pass

        #os.rename(tmp_db_file, db_file)
        
    finally:
        if tmp_db_f:
            tmp_db_f.close()
