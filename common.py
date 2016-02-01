import sys, os, yaml
import hashlib

import logging; log = logging.getLogger('common')

import config

def print_filesystem(fs_dir, out_f=sys.stdout, do_checksum=True):
    for a_file in browse_filesystem(fs_dir, do_checksum):
        if a_file is None:
            if out_f == sys.stdout:
                print("---")
            continue
        
        print_a_file(a_file, out_f)

def print_a_file(a_file, out_f):
    relpath, info = a_file[-2:]
    print("{} -> {}".format(relpath,
                            ", ".join([ "{}: {}".format(k, v) for k,v in info.items()])),
          file=out_f)

def browse_filesystem(fs_dir, do_checksum):
    for dirpath, dirnames, files in os.walk(fs_dir):
        
        for ign in config.TO_IGNORE:
            try:
                dirnames.remove(ign)
            except ValueError: pass # ign was not in the list
        dirnames.sort()
        files.sort()

        for name in sorted(files):
            fullpath = os.path.join(dirpath, name)

            relpath = fullpath[len(fs_dir)+1:]

            st = os.stat(fullpath)
            
            info = {
                "md5sum" : checksum(fullpath) if do_checksum else "",
                "size" : str(st.st_size)
                }

            yield fullpath, relpath, info
        yield None

def db_length(db_fname):
    with open(db_fname) as db_f:
        return len(db_f.readlines())
        
def browse_db(db_fname):
    with open(db_fname) as db_f:
        for line in db_f.readlines():
            relpath, _, info_txt = line[:-1].partition(" -> ")
            info_lst = info_txt.split(", ")
            info = {item.split(": ")[0]: item.split(": ")[1] for item in info_lst}

            yield relpath, info

def progress(current, total):
    print("\r%.2f%%" % (current/total*100), end="")
        
def checksum(fname):
    hashval = hashlib.md5()
        
    with open(fname, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hashval.update(chunk)
            
    return hashval.hexdigest()


class Repository():
    def __init__(self, name):
        self.name = name
        
        self.cfg_dir = os.path.join(config.CONFIG_PATH, name)
        
        self.copies_file = os.path.join(self.cfg_dir, config.COPIES_FILENAME)
        self.db_file = os.path.join(self.cfg_dir, config.DB_FILENAME)
        
        self.copyname = None
        self.tmp_dir = None
        
        self.NEW_FILES = None
        self.MISSING_FILES = None
        self.DIFFERENT_FILES = None
        self.GOOD_FILES = None
        
    def set_copyname(self, copyname):
        self.copyname = copyname
        self.tmp_dir = os.path.join(self.cfg_dir, copyname)

        self.NEW_FILES = os.path.join(self.tmp_dir, config.NEW_FILES)
        self.MISSING_FILES = os.path.join(self.tmp_dir, config.MISSING_FILES)
        self.DIFFERENT_FILES = os.path.join(self.tmp_dir, config.DIFFERENT_FILES)
        self.GOOD_FILES = os.path.join(self.tmp_dir, (config.GOOD_FILES))
                                       
    def get_copies(self, allow_new=False):
        try:
            with open(self.copies_file) as copies_f:
                return yaml.load(copies_f)
        except Exception as e:
            if os.path.exists(self.copies_file):
                log.error("Couldn't yaml-parse COPIES file {}.".format(self.copies_file))
                
            if not allow_new:
                raise FileNotFoundError(e)
            
        return {}
        
    def write_copies(self, copies):
        with open(self.copies_file, "w+") as copies_f:
            copies_f.write(yaml.dump(copies, default_flow_style=True))

def all_repositories():
    for filename in os.listdir(config.CONFIG_PATH):
        full_path = os.path.join(config.CONFIG_PATH, filename)
        
        if not os.path.isdir(full_path): continue

        yield filename, full_path

def get_repo(fs_dir):
    for reponame, repopath in all_repositories():
        repo = Repository(reponame)

        for copyname, dirname in repo.get_copies().items():
            if dirname != fs_dir:
                continue

            repo.set_copyname(copyname)
            return repo
        
    # no repo found
    return None

    
