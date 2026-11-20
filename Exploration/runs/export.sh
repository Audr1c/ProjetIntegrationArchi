#!/bin/bash

mkdir -p progress
mkdir -p formats
for fold in */; do
    fold=${fold%/}
    cp "$fold/progress.png" "progress/progress_$fold.png"
    cp "$fold/formats.png" "formats/formats$fold.png"
done