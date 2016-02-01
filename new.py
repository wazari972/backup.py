#! /usr/bin/python3

import os, shutil
import tempfile
import logging
log = logging.getLogger('root')

import backup

NOP = False

def treat_new(origin, local):
    with open(backup.NEW_FILES) as new_f:
        new_files = [f[:-1] for f in new_f.readlines()]

    tmpdir = tempfile.mkdtemp()
    
    new_dir = "{}/new_files".format(tmpdir)
    os.mkdir(new_dir)
    log.critical("New files in {}".format(new_dir))
    

    for new in list(new_files):
        filename = new.replace("/", "_")

        src = "{}/{}".format(origin, new)
        if not os.path.exists(src):
            log.warn("File {} doesn't exist anymore, update database ?".format(src))
            new_files.remove(new)
            continue
        
        os.symlink(src, "{}/{}".format(new_dir, filename))

    if not new_files:
        log.warn("No new files.")
        return

    os.system("nemo {}".format(new_dir))
    
    try:
        log.warn("Delete unwanted files in {} and press Enter to continue or ^C^C to exit.".format(new_dir))
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
        
    for new in new_files:
        filename = new.replace("/", "_")

        def save_file():
            log.critical("Copy {} from {} to {}.".format(new, origin, local))
            
            if NOP: return
        
            src = "{}/{}".format(origin, new)
            dst = "{}/{}".format(local, new)

            dst_dir = dst.rpartition("/")[0]
        
            try: os.mkdir(dst_dir)
            except FileExistsError: pass # ignore
        
            shutil.copy(src, dst)

        def delete_file():
            log.critical("Delete {} from {}.".format(new, origin))
            
            if NOP: return
            
            src = "{}/{}".format(origin, new)
            src_dir = src.rpartition("/")[0]
            
            os.remove(src)
            
            try: os.rmdir(src_dir)
            except OSError: pass # ignore
                
        if os.path.exists("{}/{}".format(new_dir, filename)):
            save_file()
        else:
            delete_file()
        
    shutil.rmtree(tmpdir)
        
if __name__ == "__main__":
    treat_new(backup.STD_PATHS["external"], backup.STD_PATHS["local"])
