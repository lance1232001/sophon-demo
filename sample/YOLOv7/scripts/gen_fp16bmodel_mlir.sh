#!/bin/bash
model_dir=$(cd `dirname $BASH_SOURCE[0]`/ && pwd)

echo model_dir is $model_dir

if [ ! $1 ]; then
    target=bm1684x
else
    target=${1,,}
    target_dir=${target^^}
    if test $target = "bm1684"
    then
        echo "bm1684 do not support fp16"
        exit
    fi
fi

outdir=../models/$target_dir

function gen_mlir()
{
    model_transform.py \
        --model_name yolov7_v0.1_3output \
        --model_def ../models/onnx/yolov7_v0.1_3output_$1b.onnx \
        --input_shapes [[$1,3,640,640]] \
        --mlir yolov7_v0.1_3output_$1b.mlir \
        --test_input ../datasets/test/3.jpg \
        --test_result yolov7_top.npz
}

function gen_fp16bmodel()
{
    model_deploy.py \
        --mlir yolov7_v0.1_3output_$1b.mlir \
        --quantize BF16 \
        --chip $target \
        --model yolov7_v0.1_3output_fp16_$1b.bmodel 
        # --test_input ../datasets/test/3.jpg \
        # --test_reference yolov7_top.npz \
        # --compare_all \
        # --tolerance 0.99,0.98 \
        # --debug 
    mv yolov7_v0.1_3output_fp16_$1b.bmodel $outdir/
    if test $target = "bm1688";then
        model_deploy.py \
            --mlir yolov7_v0.1_3output_$1b.mlir \
            --quantize F16 \
            --chip $target \
            --model yolov7_v0.1_3output_fp16_$1b_2core.bmodel \
            --num_core 2 
            # --test_input ../datasets/test/3.jpg \
            # --test_reference yolov7_top.npz \
            # --compare_all \
            # --tolerance 0.99,0.98 \
            # --debug 
        mv yolov7_v0.1_3output_fp16_$1b_2core.bmodel $outdir/
    fi
}

pushd $model_dir
if [ ! -d $outdir ]; then
    mkdir -p $outdir
fi
# batch_size=1
gen_mlir 1
gen_fp16bmodel 1

popd