Backup management tool inspired by git, with a review step but without
history.

** ALPHA VERSION, DO NOT USED WITHOUT CAREFULLY READING THE SOURCE CODE !!!**

`backup.py` keeps a database of the files saved in the repository, and
compares which files have been modified since the last update. Fast
checking is done by comparing file sizes, or, for a more consistent
but slowlier check, with `md5sum`.

The synchronization between the different copies is done after a
review step: changes are split into different categories: 
 - new files,
 - missing files,
 - modified files,
 - moved files.

The current review process is focused on images: for each of the
categories, the files are symlinked into a temporary directory, and a
file browser is launched.  At this point, the user can delete the
symlinks that should not be commited into the database. As we are
treating images, the review should be done visually, with external
tools.

Once the review is confirmed, the files are transfered. Then, the user
can refresh the state of the status files, or update the database.

INSTALL
=======

Just unzip.

Shell completion
----------------

Thanks to `docopt` package, just run these commands:

    # https://github.com/Infinidat/infi.docopt_completion
    pip install infi.docopt-completion
    sudo docopt-completion ./backup.py

backup.py init
==============

Create a new repository or connect a new backup.

backup.py init <repo-name> [--force]
-------------------------------

Initializes backup.py database and setups this directory as 'master' copy.

* <repo-name> is the name of the repository..

backup.py init from <repo-name> as <copy-name> [--force]
-----------------------------------------------------

Connects a copy of the repository name <repo-name>

* <copy-name> is the name of copy.
* <repo-name> is the name of the repository.

backup.py update
================

Updates the respository dabase with the state of the current copy.

* --checksum : Compare files with `md5sum`, not only with their size.

backup.py status
================

Compares the current copy against the repository database.

backup.py status [--force] [--checksum]
---------------------------------------------------

If there is no existing status file (or if `--force` parameter is
set), computes the state of the local copy against the database.

If there are existing status files, list their content.

* --force : Computes the status even if there are status files.
* --checksum : Compare files with `md5sum`, not only with their size.

backup.py status show
---------------------

Shows the content of the status files, if any.

backup.py status verify
-----------------------

Verifies that the content of the status files is consistent with the
current state of the copy.

backup.py status clean
----------------------

Removes the status files saved for this copy.

backup.py treat
===============

Goes through the status files and prepares a temporary directory of
symlinks for review. Files not deleted during the review are updated
according to their category (see below).

Eventually, this step (at least the review stage) should be
customizable, for instance according to the file type.

backup.py treat new [--delete]
------------------------------

Lists the files that are not present in the database.

* Files for symlinks *not* deleted are **added to the database** and **copied to the
master copy**.

* Files for symlinks deleted are untouched.

If `--delete` is passed:

* Files for symlinks *not* deleted are treated as above
* Files for symlinks *deleted* are **deleted on local copy**.

backup.py treat missing
-----------------------

Lists the files that are present in the database, but not on the
filesystem. These files are expected to be present in the master copy.

* Files for symlinks *not* deleted are **copied from the master copy**.
* Nothing is done for symlinks deleted.

If `--delete` is passed:

* Files for symlinks *not* deleted are treated as above
* Files for symlinks *deleted* are **deleted on *master* copy**.

backup.py treat updated
-----------------------

Lists the files that are different from what is stored in the
database. The master copy is expected to have the original file.
The local file is suffixed with *local*; the one from the master copy
is suffixed with *origin*.

* If *none of the two files* are deleted, **nothing happens**.
* If *one symlink is deleted*, **the file in the corresponding copy is
updated** with the remaining file.
* If *both files* are deleted, a warning is issued and **nothing is done**.

backup.py treat moved [--unmove]
------------------------------

Lists the files that have been moved between directories within the
repository. The filename is composed of the current location and the
original one.

* If the symlink is *not* deleted, **the move is issued on the master
  copy**.
* If the symlink is *deleted*, **nothing happens**.

If `--unmove` is passed:

* Symlinks *not* deleted are **untouched**.
* For symlinks *deleted*, the **file is moved to its original location**
on the current copy.

backup.py treat all [--delete] [--unmove]
-----------------------------------------

All of the above !

backup.py config 
================

Nothing yet.

backup.py debug info
====================

Prints information about repository internal files location.

