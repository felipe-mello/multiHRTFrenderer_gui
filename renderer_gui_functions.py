# -*- coding: utf-8 -*-
"""
Created on Mon Jun 26 19:46:07 2023

@author: felip
"""

import sofar
import warnings
import numpy as np
import pyaudio
from copy import deepcopy
import keyboard
import time


def sofa_setup(SOFAfiles):

    Objs = []
    samplingRate = []
    for n, name in enumerate(SOFAfiles):
        Objs.append(sofar.read_sofa(name))
        samplingRate.append(Objs[n].Data_SamplingRate)
    
    if not np.allclose(samplingRate, samplingRate):
        warnings.warn('SOFA Sampling Rates do not match\n >>>>You should NOT continue!<<<<<')
    else:
        fs = int(samplingRate[0])
        
    return Objs, samplingRate, fs


def start_audio(fs, buffer_sz, audio_in, sofaIDXmanager, SOFAfiles,
                isHeadTracker, PosManager, HTreceiver, FIRfilt, Objs,
                stop_event, idxSOFA):
    # instantiate PyAudio (1)
    p = pyaudio.PyAudio()
    stream = p.open(format=pyaudio.paFloat32,
                    channels=2,
                    rate=fs,
                    output=True,
                    frames_per_buffer=buffer_sz)

    # play stream (3)
    sigLen = audio_in.shape[0]

    data_out = np.zeros((buffer_sz, 2))
    frame_start = 0
    frame_end = frame_start + buffer_sz
    
    '''
    Changed by Felipe
    '''
    while True:
        # check if dataset has changed
        idxSOFA_tmp = idxSOFA
        if idxSOFA_tmp < len(SOFAfiles): # only update if index is within range
            idxSOFA = deepcopy(idxSOFA_tmp)

        # get head tracker position
        if isHeadTracker:
            idxPos = PosManager[idxSOFA].closestPosIdx(HTreceiver.yaw, HTreceiver.pitch, -1*HTreceiver.roll)

        # process data
        data_out = FIRfilt.process(audio_in[frame_start:frame_end, :],
                                   h=Objs[idxSOFA].Data_IR[idxPos, :, :].T)

        # output data
        data_out = np.ascontiguousarray(data_out, dtype=np.float32)
        stream.write(data_out, buffer_sz)

        # # update reading positions
        frame_start = deepcopy(frame_end)
        frame_end = frame_start + buffer_sz
        if frame_end >= sigLen:
            frame_start = 0
            frame_end = frame_start + buffer_sz
            
        if stop_event.is_set():
            break

    # stop stream (4)
    stream.stop_stream()
    stream.close()
    # close PyAudio (5)
    p.terminate()

# Not actually used...
# def savePosition(data):
#     savepos = False  
#     while True:
#         time.sleep(0.1)
#         # For using with the pointer/slide controler 
#         if keyboard.is_pressed('right'):
#             savepos = True
            
#         # take action after key release
#         if (not keyboard.is_pressed('right') and savepos):  # capture position
#             savepos = False
            
