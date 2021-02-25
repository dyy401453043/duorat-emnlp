python evaluation.py \
    --gold ./test_data/gold.txt \
    --pred ./test_data/pred.txt \
    --etype all \
    --db ../../data/database \
    --table ../../data/spider/tables.json \
    --plug_value 
    #--progress_bar_for_each_datapoint >eval.log 2>&1 &