#! /bin/sh


if [ $REPRODUCE == "lineinfile" ]
  then
    ## We are reproducing the "./" bug in lineinfile
    ## First we must revert the code that fixes the issue in lineinfile.py
    echo "reproducing lineinfile bug"
    bash /mnt/reproduce_lineinfile.sh
  fi
export ANSIBLE_TEST_RUN=testdfs