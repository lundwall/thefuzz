#! /bin/sh


if [ $REPRODUCE == "lineinfile" ]
  then
    ## We are reproducing the "./" bug in lineinfile
    ## First we must revert the code that fixes the issue in lineinfile.py
    echo "reproducing lineinfile bug"
    bash /mnt/reproduce_lineinfile.sh
elif [ $REPRODUCE = "rhsm" ]
  then
    ## We are reproducing the locale bug in rhsm
    ## First we must revert the code that fixes the issue in rhsm_repository.py
    echo "reproducing rhsm bug"
    bash /mnt/reproduce_rhsm.sh
fi
export ANSIBLE_TEST_RUN=testdfs