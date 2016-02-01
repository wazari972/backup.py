import os

import config, common

import logging; log = logging.getLogger('backup.init')

def do_info(args):
    fs_dir = os.path.abspath(".")

    log.info("Config path: {}/".format(config.CONFIG_PATH))
    
    repo = common.get_repo(fs_dir)
    if repo is None:
        log.warn("No repository found for '{}'.".format(fs_dir))
        return
    log.info("Repository:  {} ({})".format(repo.name, repo.copyname))
    log.info("Copies:".format(repo.copyname, fs_dir))

    max_size = max(map(len, repo.get_copies()))
    for copy, dirname in repo.get_copies().items():
        log.info("  {}{}--> {}".format(copy,
                                       (max_size-len(copy)+1)*" ",
                                       dirname))
        
    log.info("")
    log.info("Temporary dir: {}".format(repo.tmp_dir))
    log.info("")
    log.info("Status files:")
    max_size = max(map(len, config.STATUS_FILES))
    for status_file in config.STATUS_FILES:
        try:
            path = os.path.join(repo.tmp_dir, status_file)
            with open(path) as status_f:
                nb_lines = len(status_f.readlines())
            log.info("  {}:{}{:3d} lines".format(status_file,
                                              (max_size-len(status_file)+1)*" ",
                                              nb_lines))
        except OSError as e:
            log.info("  {}: couldn't access. ({})".format(status_file, e))
