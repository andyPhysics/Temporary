#!/usr/bin/env python 

import numpy as np
from extract_data import *
import time
import multiprocessing as mp
import uproot
from scipy.stats import chisquare
import sys,os
import uproot
import argparse


parser = argparse.ArgumentParser()
parser.add_argument("-n", "--name",type=str,default='/data/user/amedina/CosmicRay/All_updated/Proton_all.npy',
                    dest="input_file",help="name of the input file")
args = parser.parse_args()


file_name = args.input_file
loaded_dict = np.load(file_name,allow_pickle=True,encoding='latin1').item()
base = os.path.basename(file_name)
file_name_base = base.split('.')[0]
output_name = '/data/user/amedina/CosmicRay/All_updated/'+file_name_base+'_Xmax.npz'

def concat_values(file_name,dict_key):
    x = np.load(file_name,allow_pickle=True,encoding='latin1').item()
    value = x[dict_key]      
    value_all = []
    for i in value:
        for j in i:
            value_all.append(j)
    return value_all
            
depth = concat_values(file_name,'depth')
depth = [i/1000.0 for i in depth]
run = concat_values(file_name,'run')
event = concat_values(file_name,'event')
E_plus_all = concat_values(file_name,'num_EPlus')
E_minus_all = concat_values(file_name,'num_EMinus')
E_all = [i+j for i,j in zip(E_plus_all,E_minus_all)]
E_all = [i/float(max(i)) for i in E_all]
X_max = []
X_o = []
lambda_value = []
run_new = []
event_new = []
chi2_xmax = []

values = zip(run,event,depth,E_all)
count = 0
for i in values:
    print(count)
    fit = True
    try:
        output,depth_new,E_all_new = get_Xmax(i[2],i[3])
    except:
        fit = False
        count+=1
    if fit:
        chi2_xmax.append(chisquare(E_all_new,Gaisser_exp(depth_new,output[0],output[1],output[2],output[3]),ddof=3)[0])
        run_new.append(run[count])
        event_new.append(event[count])
        X_max.append(output[0]/output[1] + output[3])
        X_o.append(output[3])
        lambda_value.append(1/output[1])
        count+=1
    else:
        chi2_xmax.append(None)
        run_new.append(run[count])
        event_new.append(event[count])
        X_max.append(None)
        X_o.append(None)
        lambda_value.append(None)

new_dict = dict(run = np.hstack(run_new),
                event = np.hstack(event_new),
                X_max = np.hstack(X_max),
                X_o = np.hstack(X_o),
                lambda_value = np.hstack(lambda_value),
                chi2_xmax = np.hstack(chi2_xmax))

loaded_dict.update({'Gaisser_values':new_dict})
np.savez(output_name,loaded_dict)


