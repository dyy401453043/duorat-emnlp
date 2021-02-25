export CUDA_VISIBLE_DEVICES=3
nohup python -u scripts/train.py  \
    --config configs/duorat/duorat-cleanlink-bert-large.jsonnet  \
    --logdir logdir/duorat-bert-cleanlink \
    >train.log 2>&1 &

tail -200f train.log 