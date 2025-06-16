conda activate base

python ../../python/fermata_chopper.py \
  -i exports/bwv245.wav \
  --energy-percentile 10 \
  --stability-percentile 90 \
  --min-duration 0.1 \
  -o segments \
  --plot

conda deactivate

source ../../python/madmom-env/bin/activate   
python ../../python/add_clicks.py segments/ --clean
python ../../python/visualize_beats.py --audio-dir segments --beats-yaml detected_beats.yaml
deactivate
