#!/home/amedina/build2/bin/python
import argparse
import os
import sys,getopt
#import logging
from os.path import expandvars

from I3Tray import *
from icecube import icetray, dataclasses, dataio, toprec, recclasses, frame_object_diff,simclasses,WaveCalibrator,tpx
load('millipede')
load('stochastics')

from icecube.icetray import I3Module
from icecube.dataclasses import I3EventHeader, I3Particle
from icecube.recclasses import I3LaputopParams, LaputopParameter
from icecube.stochastics import *
from icecube.tpx import *
import multiprocessing as mp

## Are you using tableio?
from icecube.tableio import I3TableWriter
from icecube.rootwriter import I3ROOTTableService

from methods import New_fit
from my_laputop_segment import LaputopStandard

import numpy as np
from functools import partial

from methods2 import *

from icecube.frame_object_diff.segments import uncompress

## Set the log level
## Uncomment this in if you're doing code development!
icetray.set_log_level(icetray.I3LogLevel.LOG_INFO)
icetray.set_log_level_for_unit('Laputop', icetray.I3LogLevel.LOG_DEBUG)
icetray.set_log_level_for_unit('Curvature', icetray.I3LogLevel.LOG_DEBUG)

c = .299 #m/ns

parser = argparse.ArgumentParser()
parser.add_argument("-d", "--directory",type=str,default='IC86.2011',
                    dest="directory_number",help="directory number")
args = parser.parse_args()

output_directory = '/data/user/amedina/CosmicRay/Analysis_data/'

directory = args.directory_number

data_set_number = directory.split('/')[-3]

my_list = []
files = os.listdir(directory)
files_new = list(np.sort([directory + '/' + i for i in files]))
empty = False
if len(files_new) == 1:
    empty = True
else:
    my_list.append([files_new,directory.split('/')[-1],directory.split('/')[-2]])

#### PUT YOUR FAVORITE GCD AND INPUT FILE HERE


@icetray.traysegment
def ExtractWaveforms(tray, name, InputLaunches='CleanIceTopRawData',
                     OutputWaveforms='CalibratedHLCWaveforms'):

    tray.AddModule("I3WaveCalibrator", name+"_WaveCalibrator_IceTop",
                   Launches=InputLaunches,
                   Waveforms='ReextractedWaveforms',
                   Errata="ReextractedErrata")

    tray.AddModule('I3WaveformSplitter', name + '_IceTopSplitter',
                   Input = 'ReextractedWaveforms',
                   HLC_ATWD = OutputWaveforms,
                   SLC = 'CalibratedSLCWaveforms',
                   PickUnsaturatedATWD = True,  # ! do not keep all ATWDs, but only the highest non-saturated gain one                                        
                   )

def GetRiseTime(values,time,percentage):
    bin_value = 0
    for i in zip(values,time):
        if i[0] > max(values) * percentage:
            return i[1],bin_value
        bin_value+=1

class Process_Waveforms(I3Module):
    def __init__(self, context):
        I3Module.__init__(self, context)

    def Physics(self, frame):
        VEM = frame['IceTopLaputopSeededSelectedHLC'].apply(frame)
        VEM_2 = frame['IceTopLaputopSeededSelectedSLC'].apply(frame)

        waveforms = frame['IceTopVEMCalibratedWaveforms']

        HLCWaveforms = dataclasses.I3WaveformSeriesMap()

        for i in VEM.keys():
            HLCWaveforms[i] = waveforms[i]
            

        frame['LaputopHLCWaveforms'] = HLCWaveforms
        frame['LaputopHLCVEM'] = VEM
        frame['LaputopSLCVEM'] = VEM_2
        self.PushFrame(frame)

def function(t,m,s,A,t_0):
    y = A * (1/(2.*np.pi)**0.5) * (1./(s*(t-t_0))) * np.exp(-(np.log(t-t_0)-m)**2.0/(2.*s**2.0))
    return y

def chisquare_value(observed,true):
    chi2 = np.sum([((i-j)**2)/abs(j) for i,j in zip(observed,true)])

    return chi2

from scipy.optimize import curve_fit

class Extract_info(I3Module):
    def __init__(self, context):
        I3Module.__init__(self, context)

    def Physics(self, frame):
        OutputWaveformInfo = dataclasses.I3MapStringStringDouble()
        
        for i in frame['LaputopHLCWaveforms'].keys():
            key = str(i)
            waveform = np.array(frame['LaputopHLCWaveforms'][i][0].waveform)
            time = frame['LaputopHLCWaveforms'][i][0].time
            binwidth = frame['LaputopHLCWaveforms'][i][0].binwidth
            
            time_values = np.array([i*binwidth + time for i in range(len(waveform))])
            waveform_check = np.array(waveform) >= 0

            CDF = []
            CDF_value = 0
            for j in range(len(waveform)):
                if waveform_check[j]:
                    CDF_value = CDF_value + binwidth * waveform[j]
                    CDF.append(CDF_value)
                else:
                    CDF.append(CDF_value)


            fe_impedance = frame['I3Calibration'].dom_cal[i].front_end_impedance
            charge = CDF[-1]/fe_impedance
            spe_mean = dataclasses.spe_mean(frame['I3DetectorStatus'].dom_status[i],frame['I3Calibration'].dom_cal[i])

            charge_pe = charge/spe_mean


            Amplitude = 0
            count = 0
            for k in waveform:
                count+=1
                if k-Amplitude >= 0:
                    Amplitude = k
                else:
                    break

            Time_10,bin_10 = GetRiseTime(CDF,time_values,0.1)
            Time_50,bin_50 = GetRiseTime(CDF,time_values,0.5)
            Time_90,bin_90 = GetRiseTime(CDF,time_values,0.9)

            ninety_slope = (CDF[bin_90] - CDF[bin_10])/(bin_90 - bin_10)
            fifty_slope = (CDF[bin_50] - CDF[bin_10])/(bin_50 - bin_10)

            tmin = -200.0 #ns

            leading_edge = time + (bin_10 - CDF[bin_10]/ninety_slope)*binwidth
            if ninety_slope <= 0 or not np.isfinite(ninety_slope) or not (leading_edge >= time + tmin):
                leading_edge = time + tmin
            
            #trailing_edge = frame['IceTopHLCPulseInfo'][i][0].trailingEdge

            peak_time = time_values[count]

            #check_time = time_values <= trailing_edge
            check_time2 = time_values > leading_edge
            check = np.array(waveform)>0

            check = [(i and j) for i,j in zip(check_time2,check)]
            time_good = frame['LaputopHLCVEM'][i][0].time
            new_function = partial(function,t_0=time_good)

            try:
                fit = curve_fit(new_function,time_values[check],waveform[check]/np.sum(waveform[check]),bounds=((1e-10,1e-10,1e-10),np.inf),p0 = [1,1,1],maxfev=10000)
                fit_status = True
            except:
                fit_status = False
            
            if fit_status:
                chi2 = chisquare_value(waveform[check]/np.sum(waveform[check]),new_function(time_values[check],fit[0][0],fit[0][1],fit[0][2]))
                m = fit[0][0]
                s = fit[0][1]
                
                sigma_m = (fit[1][0][0])**0.5
                sigma_s = (fit[1][1][1])**0.5
            else:
                chi2 = 0
                m = 0
                s = 0
                sigma_m = 0
                sigma_s = 0 

            OutputWaveformInfo[key] = dataclasses.I3MapStringDouble()
            OutputWaveformInfo[key]['StartTime'] = time
            OutputWaveformInfo[key]['Binwidth'] = binwidth
            OutputWaveformInfo[key]['Time_50'] = Time_50
            OutputWaveformInfo[key]['Time_90'] = Time_90
            OutputWaveformInfo[key]['Time_10'] = Time_10
            OutputWaveformInfo[key]['Amplitude'] = Amplitude
            OutputWaveformInfo[key]['Charge'] = charge
            OutputWaveformInfo[key]['Charge_PE'] = charge_pe
            OutputWaveformInfo[key]['90_slope'] = ninety_slope
            OutputWaveformInfo[key]['leading_edge'] = leading_edge
            OutputWaveformInfo[key]['m'] = m
            OutputWaveformInfo[key]['s'] = s
            OutputWaveformInfo[key]['sigma_m'] = sigma_m
            OutputWaveformInfo[key]['sigma_s'] = sigma_s
            OutputWaveformInfo[key]['chi2'] = chi2
            OutputWaveformInfo[key]['fit_status'] = fit_status

        frame['WaveformInfo'] = OutputWaveformInfo
        self.PushFrame(frame)


class Get_data(I3Module):
    def __init__(self, context):
        I3Module.__init__(self, context)

    def Physics(self, frame):
        a = 4.823 * 10.0**(-4.0) #ns/m^2
        b = 19.41 #ns
        sigma = 83.5 #m
        t_cog = frame['ShowerCOG'].time
        zenith_core = frame['Laputop'].dir.zenith
        azimuth_core = frame['Laputop'].dir.azimuth
        unit_core = np.array([np.sin(zenith_core)*np.cos(azimuth_core),
                              np.sin(zenith_core)*np.sin(azimuth_core),
                              np.cos(zenith_core)])

        output_map = dataclasses.I3RecoPulseSeriesMap()
 
        Laputop = frame['Laputop']
        x_core = np.array([Laputop.pos.x,Laputop.pos.y,Laputop.pos.z])
        t_core = Laputop.time
        theta = Laputop.dir.theta 
        phi = Laputop.dir.phi
        n = np.array([np.sin(theta) * np.cos(phi) , np.sin(theta) * np.sin(phi), np.cos(theta)])

        radius = dataclasses.I3MapKeyVectorDouble()
        radius_old = dataclasses.I3MapKeyVectorDouble()
        m = dataclasses.I3MapKeyVectorDouble()
        s = dataclasses.I3MapKeyVectorDouble()
        chi2 = dataclasses.I3MapKeyVectorDouble()
        sigma_m = dataclasses.I3MapKeyVectorDouble()
        sigma_s = dataclasses.I3MapKeyVectorDouble()

        for i in frame['LaputopHLCVEM'].keys():
            output_map[i] = dataclasses.I3RecoPulseSeries()

            pulse = dataclasses.I3RecoPulse()

            vec = []
            vec_old = []
            vec_m = []
            vec_s = []
            vec_chi2 = []
            vec_sigma_m = []
            vec_sigma_s = []
            for j in frame['LaputopHLCVEM'][i]:
                pulse.charge = j.charge

                time = j.time
                position_dom = frame['I3Geometry'].omgeo[i].position
                x_dom = np.array([position_dom.x , position_dom.y , position_dom.z])

                Radius = np.dot(x_dom-x_core,x_dom-x_core)**0.5
                unit_dom = (x_dom-x_core)/Radius
                true_radius = np.dot(unit_dom-unit_core,x_dom-x_core)

                time_signal = time
            
                vec.append(true_radius)
                vec_old.append(Radius)
                key = str(i)
                pulse.time = frame['LaputopHLCVEM'][i][0].time
                vec_m .append(frame['WaveformInfo'][key]['m'])
                vec_s.append(frame['WaveformInfo'][key]['s'])
                vec_chi2.append(frame['WaveformInfo'][key]['chi2'])
                vec_sigma_m.append(frame['WaveformInfo'][key]['sigma_m'])
                vec_sigma_s.append(frame['WaveformInfo'][key]['sigma_s'])

                output_map[i].append(pulse)

            radius[i] = np.array(vec)
            radius_old[i] = np.array(vec_old)
            m[i] = np.array(vec_m)
            s[i] = np.array(vec_s)
            chi2[i] = np.array(vec_chi2)
            sigma_m[i] = np.array(vec_sigma_m)
            sigma_s[i] = np.array(vec_sigma_s)

        frame['All_radius'] = radius
        frame['All_radius_old'] = radius_old
        frame['All_pulses'] = output_map
        frame['m'] = m
        frame['s'] = s
        frame['chi2'] = chi2
        frame['sigma_m'] = sigma_m
        frame['sigma_s'] = sigma_s
        self.PushFrame(frame)

def function_m(X,m_o,m_r,m_s,m_s2):
    s,rho = X
    m = m_o + m_r * rho 
    #+ m_s2*(s-m_s)**2
    return m

def function_s(rho,s_o,s_r):
    s = s_o + s_r * rho
    return s

def get_check(function,s,rho,m,sigmam,sigmas,charge,chi2):
    check = (rho<400)&(sigmam<0.1)&(sigmas<0.1)&(charge>0.25)&(chi2>0)&(chi2<10)
    error = np.array([1/i for i in sigmam])
    fit_m = curve_fit(function,xdata=[s[check],rho[check]],ydata=m[check],bounds=((1e-10,1e-10,1e-10,1e-10),np.inf))
    
    new_m = function([s,rho],fit_m[0][0],fit_m[0][1],fit_m[0][2],fit_m[0][3])
    check = (np.array([(abs(i-j)/j)*100 for i,j in zip(new_m,m)])<=10)&check
    
    return check

def get_check_s(function,rho,s,sigmas,check):
    error = np.array([1/i for i in sigmas])
    fit_s = curve_fit(function,xdata=rho[check],ydata=s[check],bounds=((1e-10,1e-10),np.inf),sigma=error[check])

    new_s = function(rho,fit_s[0][0],fit_s[0][1])
    check = (np.array([(abs(i-j)/j)*100 for i,j in zip(new_s,s)])<=10)&check

    return check

class Get_fit(I3Module):
    def __init__(self, context):
        I3Module.__init__(self, context)

    def Physics(self, frame):
        xc = frame['Laputop'].pos.x
        yc = frame['Laputop'].pos.y
        zc = frame['Laputop'].pos.z
        azimuth = frame['Laputop'].dir.azimuth
        zenith = frame['Laputop'].dir.zenith
        x = []
        y = []
        z = []
        m = []
        s = []
        chi2 = []
        sigmas = []
        sigmam = []
        VEM = []
        for key in frame['LaputopHLCVEM'].keys():
            omkey = str(key)
            if frame['WaveformInfo'][omkey]['chi2']!=0:
                m.append(frame['WaveformInfo'][omkey]['m'])
                s.append(frame['WaveformInfo'][omkey]['s'])
                chi2.append(frame['WaveformInfo'][omkey]['chi2'])
                position = frame['I3Geometry'].omgeo[key].position
                x.append(position.x)
                y.append(position.y)
                z.append(position.z)
                VEM.append(frame['LaputopHLCVEM'][key][0].charge)
                sigmas.append(frame['WaveformInfo'][omkey]['sigma_s'])
                sigmam.append(frame['WaveformInfo'][omkey]['sigma_m'])


        x_new = [i-xc for i in x]
        y_new = [i-yc for i in y]
        z_new = [i-zc for i in z]

        vector = [[i,j,k] for i,j,k in zip(x_new,y_new,z_new)]

        vector_new =[new_vector(i,azimuth,zenith) for i in vector]
        
        try:
            z_corrected = np.array(list(zip(*vector_new))[0])
            rho = np.array(list(zip(*vector_new))[1])
        except IndexError:
            z_corrected = np.array([])
            rho = np.array([])
            print('something is wrong here')
            print(vector_new)
        m = np.array(m)
        s = np.array(s)
        chi2 = np.array(chi2)
        sigmas = np.array(sigmas)
        sigmam = np.array(sigmam)
        VEM = np.array(VEM)
        output_map_m = dataclasses.I3MapStringDouble()
        output_map_s = dataclasses.I3MapStringDouble()
        #m_fit

        try:
            check = get_check(function_m,s,rho,m,sigmam,sigmas,np.log10(VEM),chi2)
            fit_m = curve_fit(function_m,xdata=[s[check],rho[check]],ydata=m[check],bounds=((1e-10,1e-10,1e-10,1e-10),np.inf))
            
            output_map_m['m_o'] = fit_m[0][0]
            output_map_m['m_r'] = fit_m[0][1]
            output_map_m['m_s'] = fit_m[0][2]
            output_map_m['m_s2'] = fit_m[0][3]
            output_map_m['m_125'] = function_m([fit_m[0][2],125],fit_m[0][0],fit_m[0][1],fit_m[0][2],fit_m[0][3])
            chi2_m = chisquare_value(m[check],function_m(np.array([s[check],rho[check]]),fit_m[0][0],fit_m[0][1],fit_m[0][2],fit_m[0][3]))
            print('chi2_m: ',chi2_m)
            output_map_m['chi2'] = chi2_m
            output_map_m['fit_status'] = 1
            output_map_m['s_mean'] = np.mean(s[check])
            output_map_m['s_std'] = np.std(s[check])
            failed = False

        except (ValueError,TypeError,RuntimeError) as err:
            failed = True

        try:
            if failed:
                check = (np.log10(VEM)>0.5)&(chi2>0)&(chi2<10)
                fit_m = curve_fit(function_m,xdata=[s[check],rho[check]],ydata=m[check],bounds=((1e-10,1e-10,1e-10,1e-10),np.inf))

                output_map_m['m_o'] = fit_m[0][0]
                output_map_m['m_r'] = fit_m[0][1]
                output_map_m['m_s'] = fit_m[0][2]
                output_map_m['m_s2'] = fit_m[0][3]
                output_map_m['m_125'] = function_m([fit_m[0][2],125],fit_m[0][0],fit_m[0][1],fit_m[0][2],fit_m[0][3])
                chi2_m = chisquare_value(m[check],function_m(np.array([s[check],rho[check]]),fit_m[0][0],fit_m[0][1],fit_m[0][2],fit_m[0][3]))
                print('chi2_m: ',chi2_m)
                output_map_m['chi2'] = chi2_m
                output_map_m['fit_status'] = 2
                output_map_m['s_mean'] = np.mean(s[check])
                output_map_m['s_std'] = np.std(s[check])

        

        except (ValueError,TypeError,RuntimeError) as err:
            output_map_m['m_o'] = 0
            output_map_m['m_r'] = 0
            output_map_m['m_s'] = 0
            output_map_m['m_s2'] = 0
            output_map_m['m_125'] = 0
            output_map_m['chi2'] = 0
            output_map_m['fit_status'] = 0

        try:
            check = get_check(function_m,s,rho,m,sigmam,sigmas,np.log10(VEM),chi2)
            check = get_check_s(function_s,rho,s,sigmas,check)
            error = np.array([1/i for i in sigmas])
            fit_s = curve_fit(function_s,xdata=rho[check],ydata=s[check],sigma=error[check],bounds=((1e-10,1e-10),np.inf))

            output_map_s['s_o'] = fit_s[0][0]
            output_map_s['s_r'] = fit_s[0][1]
            chi2_s = chisquare_value(s[check],function_s(np.array(rho[check]),fit_s[0][0],fit_s[0][1]))
            print('chi2_s: ',chi2_s)
            output_map_s['chi2'] = chi2_s
            output_map_s['fit_status'] = 1

        except (ValueError,TypeError,RuntimeError) as err:
            output_map_s['s_o'] = 0
            output_map_s['s_r'] = 0
            output_map_s['chi2'] = 0
            output_map_s['fit_status'] = 0

        frame['m_fit'] = output_map_m
        frame['s_fit'] = output_map_s

        self.PushFrame(frame)

def function2(i):
    I3_OUTFILE = output_directory + data_set_number + '_%s_%s'%(i[1],i[2])+ '.i3.bz2'
    ROOTFILE = output_directory + data_set_number + '_%s_%s'%(i[1],i[2]) + '.root'

    tray = I3Tray()

    ########## SERVICES FOR GULLIVER ##########

    #------------------- LET'S RUN SOME MODULES!  ------------------

    #**************************************************
    #                 Reader and whatnot
    #**************************************************

    datareadoutName = 'IceTopLaputopSeededSelectedHLC'
    badtanksName= "BadDomsList"
    print(i[0])
    tray.AddModule("I3Reader","reader")(("FileNameList", i[0]))
    

    tray.Add(uncompress)
    # Extract HLC pulses
    #tray.AddModule('I3TopHLCPulseExtractor', 'TopHLCPulseExtractor',
    #               PulseInfo = 'IceTopHLCPulseInfo',        # PulseInfo: amplitude, rise time, etc. Empty string to disable
    #               Waveforms = 'IceTopVEMCalibratedHLCWaveforms',   # Input HLC waveforms from WaveCalibrator
    #           )
    
    tray.AddModule(Process_Waveforms,'Process_wavefomrs')
    
    tray.AddModule(Extract_info)
    
    tray.AddModule(Get_data)

    tray.AddSegment(LaputopStandard,"Laputop_new", pulses='LaputopHLCVEM')

    tray.AddModule(Get_fit)

    tray.AddModule("I3Writer","EventWriter")(
        ("DropOrphanStreams", [icetray.I3Frame.DAQ]),
        ("Filename",I3_OUTFILE),
    )

    wanted_inice_reco=["Millipede",
                       "MillipedeFitParams",
                       "Millipede_dEdX",
                       "Stoch_Reco",
                       "Stoch_Reco2",
                       "I3MuonEnergyLaputopCascadeParams",
                       "I3MuonEnergyLaputopParams"
    ]

    wanted_inice_cuts=['IT73AnalysisInIceQualityCuts']

    wanted_general = ['I3EventHeader',
                      'CalibratedHLCWaveforms',
                      'CalibratedSLCWaveforms',
                      'LaputopHLCWaveforms',
                      'IceTopWaveformWeight',
                      'IceTopVEMCalibratedWaveforms',
                      'IceTopHLCPEPulses',
                      #'IceTopHLCPulseInfo',
                      'IceTopHLCVEMPulses',
                      'IceTopSLCPEPulses',
                      'IceTopSLCVEMPulses',
                      'LaputopHLCVEM',
                      'LaputopSLCVEM',
                      'Laputop',
                      'LaputopParams',
                      'Laputop_new',
                      'Laputop_newParams'
                      'All_pulses',
                      'All_radius',
                      'All_radius_old',
                      'ShowerCOG',
                      'm',
                      's',
                      'chi2',
                      'sigma_m',
                      'sigma_s'
                  ]


    ## Output root file
    root = I3ROOTTableService(ROOTFILE,"aTree")
    tray.AddModule(I3TableWriter,'writer')(
        ("tableservice", root),
        ("keys",wanted_general+wanted_inice_reco+wanted_inice_cuts),
        ("subeventstreams",['InIceSplit',"ice_top"])
    )



   
    # Execute the Tray
    # Just to make sure it's working!
    tray.Execute()

if not empty:
    pool = mp.Pool(5)
    pool.map(function2,my_list)
