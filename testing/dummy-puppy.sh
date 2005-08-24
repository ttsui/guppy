#!/bin/bash

echo ARG COUNT = $#
for i in `seq $#`; do
	echo ARG $i = `eval echo '$'$i`
done
