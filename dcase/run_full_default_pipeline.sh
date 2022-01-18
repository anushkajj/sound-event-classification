cd /notebooks/
python compute_logmel.py /notebooks/sonyc_urban_sound_tagging/train /notebooks/dcase/data/logmelspec/train
python compute_logmel.py /notebooks/sonyc_urban_sound_tagging/validate /notebooks/dcase/data/logmelspec/validate
cd dcase/
python statistics.py -f logmelspec -n 128
python parse_dcase.py
python train.py -f logmelspec -n 636 --seed 42
python evaluate.py -f logmelspec -n 636 