#!/usr/bin/python

import uproot
import numpy as np
import argparse
import pandas as pd

train_files = ["Helium_train.root","Proton_train.root","Iron_train.root","Oxygen_train.root"]
test_files = ["Helium_test.root","Proton_test.root","Iron_test.root","Oxygen_test.root"]
verification_files = ["Helium_verify.root","Proton_verify.root","Iron_verify.root","Oxygen_verify.root"]

from sklearn.preprocessing import minmax_scale


#----------------------------------------------------------------------------
def get_data(input_file_list):
    path = '/data/ana/CosmicRay/IT73-IC79_3ySpectrumAndComposition/simulation/AllSim_merged'
    filelist = input_file_list
    labels = []
    features = []

    for i in filelist:
        f = uproot.open(path+'/'+i)
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
       

        x = zip(Energy)
        y = zip(S125,np.cos(Zenith),MeanEnergyLoss,HE_stoch_standard,HE_stoch_strong)
        features += y
        labels += x
    features = np.array(features)
    labels = np.array(labels)
    return labels,features


train_labels,train_features = get_data(train_files)
test_labels,test_features = get_data(test_files)

import keras
from keras import initializers
from keras.layers import Dense, Dropout, Flatten, Input, Concatenate
from keras.models import Model
import keras.backend as K
from tensorflow.python.framework import ops
from tensorflow.python.ops import gen_math_ops as math_ops

best_model = keras.callbacks.ModelCheckpoint('Energy_best.h5',
                                             monitor='val_loss',
                                             save_best_only=True,
                                             save_weights_only=False,
                                             mode='auto')

input_layer = Input(shape=(5,))

model1 = Dense(7,activation='tanh',use_bias=True,bias_initializer=initializers.Constant(0.1))(input_layer)

model1 = Dropout(0.5)(model1)

model1 = Dense(4,activation='tanh',use_bias=True,bias_initializer=initializers.Constant(0.1))(model1)

model1 = Concatenate(axis=-1)([model1,input_layer])

predictions = Dense(1,activation='linear')(model1)

model = Model(inputs=input_layer,outputs=predictions)

opt = keras.optimizers.RMSprop(decay=1e-5)

model.compile(optimizer=opt , loss = 'mse')

history = model.fit(train_features,train_labels,
                    epochs=10,
                    validation_data = (test_features,test_labels),
                    callbacks=[best_model])

model.save('Energy_model.h5')

loss = zip(history.history['loss'],history.history['val_loss'])

np.savetxt('Energy_model.csv',loss,delimiter=',')
