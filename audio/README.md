## cf. requirements_librosa.txt
conda activate base
cd bwv245
python ../fermata_chopper.py \
  -i exports/bwv245.wav \
  --energy-percentile 10 \
  --stability-percentile 90 \
  --min-duration 0.1 \
  -o segments \
  --plot
cd ..
conda deactivate

## cf. requirements_madmom.txt
source ~/.venvs/madmom/bin/activate 
cd bwv245
python ../add_clicks.py segments/ --clean
python ../visualize_beats.py --audio-dir segments --beats-yaml detected_beats.yaml
cd ..
deactivate
