#!/bin/bash

cd ..

for rep in testing/*/; do
    if [ -f "${rep}test.py" ]; then
        echo -e "\nTesting $rep:"
        python "${rep}test.py"
    fi
done
