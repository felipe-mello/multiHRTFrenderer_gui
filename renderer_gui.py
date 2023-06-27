# -*- coding: utf-8 -*-
"""
Created on Mon Jun 26 16:57:57 2023

@author: felip
"""

'''
Real time HRTF renderer.

Multiple SOFA files can be loaded and arbitrarily switched using UDP messages
Authors: Davi Rocha Carvalho
'''

# %% Import libs

import pyaudio
import threading
import numpy as np
import soundfile as sf
from copy import deepcopy
from FIRconv import FIRfilter
from geometry import GeomtryFunctions
from EACheadtracker import HeadTracker
from positionReceiver import PositionReceiver
from datasetIndexReceiver import DatasetIndexReceiver

# GUI prototype
import os
import PySimpleGUI as sg
import renderer_functions as rfx


# %% Global configs ##################################################################
# head tracker data receiver config
isHeadTracker = True
HT_IP = '127.0.0.1'
HT_PORT = 5555
CAM_ID = 0  # select index of camera feed

# dataset remote receiver config
DS_IP = '0.0.0.0'
DS_PORT = 5556

# audio rendering config
buffer_sz = 512
method = 'upols'  # FIR method

# 
SOFAfiles_tmp = []

# Source position
''' NOTE os angulos são em coordenadas "navigacionais"
    -180 < azimute < 180
    -90 < elevação < 90
    tal que 0° é diretamente a frente,
    elevação=90: topo
    azimute negativo: direita
'''
src_azim = 0  # azimute
src_elev = 0   # elevação

###############################################################################
# %% GUI setup

sofa_files = os.listdir('SOFA/')
audio_files = os.listdir('Audio/')

font = ("OpenSans", 16)

layout = [
        [sg.OptionMenu(values=audio_files, default_value='Audio File', key="-AUDIO_FILE-", size=(20,20)),
         sg.OptionMenu(values=sofa_files, default_value='HRTF 1', key="-HRTF_1-", size=(20,20)),
         sg.OptionMenu(values=sofa_files, default_value='HRTF 2', key="-HRTF_2-", size=(20,20)),
        ],
            
        [sg.Button('Setup', size=(10,2), font=font, button_color="orange"), 
         sg.Button('Start', size=(10,2), font=font, button_color="green"), 
         sg.Button('Exit', size=(10,2), font=font, button_color="red")]   
    ]

window = sg.Window('multiHRTFrenderer', layout, element_justification='c', font=font)

while True:
    event, values = window.read()
    
    # Break the GUI operation if window is closed
    if window.is_closed() or event=='Exit':
        window.close()
        os._exit(00)
        break
 
 #################################################################################################
 #################################################################################################   
 
    # Subjective test configuration
    if event=='Setup':
        
        # Set the audio file to be played
        audioPath = values['-AUDIO_FILE-']
        audioPath = 'Audio/' + audioPath
        print(audioPath)
        
        # Set the SOFA files to be loaded
        SOFAfiles_tmp.extend([values['-HRTF_1-'], values['-HRTF_2-']])
        SOFAfiles = ['SOFA/' + tmp for tmp in SOFAfiles_tmp]
        
        # Load and organize the SOFA files (following Davi's variables)
        sofaData = rfx.sofa_setup(SOFAfiles) # special function
        Objs = sofaData[0]
        samplingRate = sofaData[1]
        fs = sofaData[2]
        
        # Initialize Dataset Index Receiver
        sofaIDXmanager = DatasetIndexReceiver(IP_rcv=DS_IP, PORT_rcv=DS_PORT,
                                              IP_snd=HT_IP, PORT_snd=HT_PORT)
        
        # Audio input
        audio_in, _ = sf.read(audioPath,
                              samplerate=None,
                              always_2d=True,
                              dtype=np.float32)  # input signal
        audio_in = np.mean(audio_in, axis=1, keepdims=True)
        N_ch = audio_in.shape[-1]
        
        # Initialize headtracker
        if isHeadTracker:
            thread = threading.Thread(target=HeadTracker.start, args=(CAM_ID, HT_PORT), daemon=False)  # track listener position
            thread.start()
            HTreceiver = PositionReceiver(IP=HT_IP, PORT=HT_PORT)  # read head tracker position data

            # convert positions to navigational coordinates for ease to use
            def sph2cart(posArray):
                idx = np.where(posArray[:, 0] > 180)[0]
                posArray[idx, 0] = posArray[idx, 0] - 360
                return posArray

            for n in range(len(Objs)):
                Objs[n].SourcePosition = sph2cart(Objs[n].SourcePosition)

        # initialize position index manager
        PosManager = []
        for Obj in Objs:
            PosManager.append(GeomtryFunctions(Obj.SourcePosition, src_azim, src_elev))
            
        # Initialize FIR filter
        idxSOFA = 0
        idxPos = PosManager[idxSOFA].closestPosIdx(yaw=0, pitch=0, roll=0)
        FIRfilt = FIRfilter(method, buffer_sz, h=Objs[idxSOFA].Data_IR[idxPos, :, :].T)
        
#################################################################################################
#################################################################################################

    # Start the test
    if event=='Start':
        audio_thread = threading.Thread(target=rfx.start_audio,
                                        args=(fs, buffer_sz, audio_in,
                                              sofaIDXmanager, SOFAfiles,
                                              isHeadTracker, PosManager,
                                              HTreceiver, FIRfilt, Objs), daemon=False)
        audio_thread.start()
    
    
'''
Próximos passos:
    i) salvar quando a pessoa aperta o espaço
    ii) validar a posição na tela (para o operador ver)
    iii) trocar de HRTF+posição
    iv) Ajustar o 'fechamento' das coisas
    
'''
 



