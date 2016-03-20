import os

CONFIG_PATH = os.path.join(os.path.expanduser("~"), ".config", "backup.py")
DB_FILENAME = "db.txt"
COPIES_FILENAME = "copies"

DEFAULT_FS_DIR = "/var/webalbums"

TO_IGNORE = [".git", "Other", "tmp", "VIDEO"]

NEW_FILES = "new.txt"
MISSING_FILES = "missing.txt"
DIFFERENT_FILES = "different.txt"
GOOD_FILES = "good.txt"

STATUS_FILES = MISSING_FILES, DIFFERENT_FILES, NEW_FILES, GOOD_FILES

STATUS_FILES_DESC = ((GOOD_FILES, "Good files"),
                    (MISSING_FILES, "Missing files"),
                    (DIFFERENT_FILES, "Different files"),
                    (NEW_FILES, "New files"))

NOP = False
