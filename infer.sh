export CUDA_VISIBLE_DEVICES=1

python scripts/infer_questions.py \
        --logdir ./logdir/duorat-bert \
        --data-config data/val.libsonnet \
        --questions data/spider/dev.json \
        --output-spider ./logdir/duorat-bert/val_step_100000.json #\
       # >train.log 2>&1 &