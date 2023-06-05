#!/bin/bash
res=$(dpkg -l|grep unzip)
if [ $? != 0 ];
then
    echo "Please install unzip on your system!"
    exit
fi
res=$(pip3 list|grep dfn)
if [ $? != 0 ];
then
    pip3 install dfn
fi
scripts_dir=$(dirname $(readlink -f "$0"))

pushd $scripts_dir
# datasets
if [ ! -d "../datasets" ]; 
then
    python3 -m dfn --url http://219.142.246.77:65000/sharing/JWymbuanL
    unzip datasets.zip -d ../
    rm datasets.zip

    echo "datasets download!"
else
    echo "Datasets folder exist! Remove it if you need to update."
fi

# models
if [ ! -d "../models" ]; 
then
    python3 -m dfn --url http://219.142.246.77:65000/sharing/NgoRmzlzW
    unzip models.zip -d ../
    rm models.zip
    rm ../models/BM1684/ch_PP-OCRv3_*_int8.bmodel ../models/BM1684X/ch_PP-OCRv3_*_int8.bmodel
    echo "models download!"
else
    echo "Models folder exist! Remove it if you need to update."
fi
popd