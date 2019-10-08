import uproot
import numpy as np
import argparse
import pandas as pd
import keras.backend as K
from tensorflow.python.framework import ops
from tensorflow.python.ops import gen_math_ops as math_ops


verification_files = ["Helium_verify.root","Proton_verify.root","Iron_verify.root","Oxygen_verify.root"]

from sklearn.preprocessing import minmax_scale
from keras.models import load_model

#----------------------------------------------------------------------------
def get_data(input_file_list):
    path = '/data/ana/CosmicRay/IT73-IC79_3ySpectrumAndComposition/simulation/AllSim_merged'
    filelist = input_file_list
    labels = []
    features = []

    for i in filelist:
        f = uproot.open(path+'/'+i)
        Mass = f['tinyTree']['mass'].array()
        Mass = np.log(Mass)
        Mass = [1+(3.0/4.0)*i for i in Mass]
        Energy = f['tinyTree']['energy'].array()
        Energy = np.log10(Energy)
        S125 = f['tinyTree']['s125'].array()
        S125 = np.log10(S125)
        Zenith= f['tinyTree']['zenith'].array()
        EnergyLoss = zip(f['tinyTree']['eloss_1500'].array(),f['tinyTree']['eloss_1800'].array(),f['tinyTree']['eloss_2100'].array(),f['tinyTree']['eloss_2400'].array())
        MeanEnergyLoss = [np.mean(i) for i in EnergyLoss]
        MeanEnergyLoss = np.log10(MeanEnergyLoss)
        HE_stoch_standard = f['tinyTree']['n_he_stoch'].array()
        HE_stoch_strong = f['tinyTree']['n_he_stoch2'].array()
       

        x = zip(Energy,Mass)
        y = zip(S125,np.cos(Zenith),MeanEnergyLoss,HE_stoch_standard,HE_stoch_strong)
        features += y
        labels += x

    features = np.array(features)
    labels = np.array(labels)
    return labels,features


#def custom_loss(ytrue,ypred):
#    y_pred1 = ops.convert_to_tensor(ypred[0])
#    y_pred2 = ops.convert_to_tensor(ypred[1])

#    y_true1 = math_ops.cast(ytrue[0], ypred[0].dtype)
#    y_true2 = math_ops.cast(ytrue[1], ypred[1].dtype)

#    return K.mean(math_ops.square(y_pred1 - y_true1), axis=-1)+10.0*K.mean(math_ops.square(y_pred2 - y_true2), axis=-1)


labels,features = get_data(verification_files)

model = load_model('NN_best.h5')

label_predict = []
label_true = []

for i in verification_files:
    x,y = get_data([i])
    labels_pred = model.predict(y)
    label_true.append(x)
    label_predict.append(labels_pred)

output_labels = model.predict(features)

print(output_labels)

output = {'true':labels,'pred':output_labels}

labels_dict = {'true':label_true,'pred':label_predict}

np.save('All_output.npy',output)
np.save('All_split.npy',labels_dict)