#!/bin/bash

export PYTHONPATH="$PYTHONPATH:/lerepairedeletalon/server/current/test:/lerepairedeletalon/server/current/bin"

for rep in */; do
    if [ -f "${rep}test.py" ]; then
        echo -e "\nTesting $rep:"
        python "${rep}test.py"
    fi
done
