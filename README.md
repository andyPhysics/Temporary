# CosmicRay
Analysis of CosmicRay Composition
Author: Andres Medina
Institution: The Ohio State University

This code takes works with simulation data found in the following directory:
/data/user/amedina/CosmicRay

You will find the following directories:

Analysis -- I3files and root files with curvature and thickness fit

Analysis_data -- I3files and root files with curvature and thickness fit for experimental data

csv_files -- csv files containing all the necessary information for training networks

csv_files_data -- csv files containing all the necessary information for the experimental data

I3_files -- I3files that only contains coincident events, these are the files that are use to
 calculate the curvature and thickness. Contains also waveforms
 
I3_files_data -- I3files that only contains coincident events, these are the files that are used to calculate curvature and thickness for experimentald data. Contains waveforms and is a 10\% cut. 

## Top Level
 
Majority of the top level files are those used for data comparisons and extracting the necessary variables and reconstructions

###ipython notebooks

Check-fit.ipynb -- File used to check the fit for thickness parameters

Untitled.ipynb -- Extracts a waveform, for checks

### python files

Main files for the analysis to extract and reconstruct the files:

analysis.py -- Analysis file that performs the curvature and thickness reconstruction

analysis_data.py -- Analysis file that performs the curvature and thickness reconstruction for experimental data

curvature.py -- previous version of curvature

get_event.py -- file used to extract about 1000 events to produce Events.csv. This is for checking fits of the thickness parameters done in Check-fit.ipynb

waveform_extract_2.py -- File used to extract necessary events and only those that have coincident events and have waveforms. 

waveform_extract_data.py -- File used to extract necessary events and only those that have coincident events and have waveforms for experimental data

my_laputop_segment.py -- laputop segment used for curvature reconstruction in analysis

The three files below provide the methods for changing basis and those necessary for thickness reconstruction variables. 

methods.py 

methods2.py

vectorDiff.py

### Submitting files

analysis.sh -- file to run analysis

waveform_extract.sh -- obtain waveform files which are those in I3Files above

waveform_extract_data.sh -- obtain waveform files which are those in I3Files_data above

output_files.sh -- just creates list of files to be analyzed. 

Most of these files are run either in cobalt or you could run them by ./ > filename

## ipython_curvature

Feel free to ignore

## NN

**files -- This contains all the information needed to train the network



