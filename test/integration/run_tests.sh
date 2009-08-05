#!/bin/bash

export BASE_DIR=../..
export PATH=${BASE_DIR}/guppy/:${BASE_DIR}/test/fakepuppy/:$PATH

for TEST in *.py; do
	echo "Running [$TEST]"
	python $TEST
done
