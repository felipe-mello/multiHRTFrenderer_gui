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
import time
import random
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
        [sg.Text('Enter the subject name (ex: john_cage)', font=font, justification='center')],
    
        [sg.InputText('', key='-SUBJECT-', font=font, justification='center')],
    
        [#sg.OptionMenu(values=audio_files, default_value='Audio File', key="-AUDIO_FILE-", size=(20,20)),
         sg.OptionMenu(values=sofa_files, default_value='HRTF 1', key="-HRTF_1-", size=(20,20), pad=(5,20)),
         sg.OptionMenu(values=sofa_files, default_value='HRTF 2', key="-HRTF_2-", size=(20,20), pad=(5,20)),
        ],
        
        [sg.Button('Setup', size=(10,2), font=font, button_color="orange", pad=(20,20)),
         sg.Button('Start', size=(10,2), font=font, button_color="green", pad=(20, 20), disabled=True, key='-START-')],
        
        [sg.Text('Wating for setup...', key='-STATUS_TEXT-', font=("OpenSans", 20), justification='center', pad=(0, 20))],
        
        [sg.Button('Next audio', key='-NEXT-', size=(25,2), font=font, disabled=True, pad=(0, 20))],
        
        [sg.Text('', key='-TEST_SEQ-', font=("OpenSans", 12), justification='center', pad=(0,20))]
        
    ]

window = sg.Window('multiHRTFrenderer', layout, element_justification='c', font=font)

while True:
    event, values = window.read()
    
    # Break the GUI operation if window is closed
    if window.is_closed(): # or event=='Exit':
        window.close()
        os._exit(00)
        break
 
 #################################################################################################
 #################################################################################################   
 
    # Subjective test configuration
    if event=='Setup':
        
        # Create a directory with subject's name
        if not os.path.exists('subjects'):
            os.makedirs('subjects')
        elif not os.path.exists('subjects/' + values['-SUBJECT-']):
            os.makedirs('subjects/' + values['-SUBJECT-'])
            
        save_path= 'subjects/' + values['-SUBJECT-']
        
        # Set a random test sequence
        az = [30, 0]
        el = [30, 70]
        hrtf = ['hrtf 1', 'hrtf 2']
        seq = []

        for ii in range(len(az)):
            seq.append([az[ii], el[ii], hrtf[0]])
            
        for ii in range(len(az)):
            seq.append([az[ii], el[ii], hrtf[1]])
            
        random.shuffle(seq)
            
        # Set the audio file to be played
        testCounter = 0
        audioCounter = 0
        audioPath = ['Audio/drums.wav', 'Audio/sabine.wav']
        
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
        audio_in, _ = sf.read(audioPath[0],
                              samplerate=None,
                              always_2d=True,
                              dtype=np.float32)  # input signal
        audio_in = np.mean(audio_in, axis=1, keepdims=True)
        N_ch = audio_in.shape[-1]
        
        # Initialize headtracker
        if isHeadTracker:
            thread = threading.Thread(target=HeadTracker.start, args=(CAM_ID, HT_PORT), daemon=False)  # track listener position
            thread.start()
            # HTreceiver = PositionReceiver(save_path, IP=HT_IP, PORT=HT_PORT)  # read head tracker position data

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
            PosManager.append(GeomtryFunctions(Obj.SourcePosition, seq[testCounter][0], seq[testCounter][1]))
            
        # Initialize FIR filter
        if seq[testCounter][2] == 'hrtf 1':    
            idxSOFA = 0
        elif seq[testCounter][2] == 'hrtf 2': 
            idxSOFA = 1
        idxPos = PosManager[idxSOFA].closestPosIdx(yaw=0, pitch=0, roll=0)
        FIRfilt = FIRfilter(method, buffer_sz, h=Objs[idxSOFA].Data_IR[idxPos, :, :].T)
        
        # Stop event for the audio thread
        stop_event = threading.Event()
        
        time.sleep(5)
        window['-START-'].update(disabled=False)
        window['-STATUS_TEXT-'].update('Setup complete! Click Start to begin the test.')
        
#################################################################################################
#################################################################################################

    # Start the test
    if event=='-START-':
        
        window['-NEXT-'].update(disabled=False)
        window['-STATUS_TEXT-'].update('Test audio number: ' + str(testCounter))
        
        # Initialize PositionReceiver
        if isHeadTracker:
            HTreceiver = PositionReceiver(save_path, IP=HT_IP, PORT=HT_PORT)  # read head tracker position data
        
        audio_thread = threading.Thread(target=rfx.start_audio,
                                        args=(fs, buffer_sz, audio_in,
                                              sofaIDXmanager, SOFAfiles,
                                              isHeadTracker, PosManager,
                                              HTreceiver, FIRfilt, Objs,
                                              stop_event, idxSOFA), daemon=False)
        audio_thread.start()

##################################################################################################
##################################################################################################

    if event=='-NEXT-':
        
        # Stop last audio
        stop_event.set()
        testCounter += 1
        
        # Redo the sequence for the second audio
        if testCounter >= len(seq):
            audioCounter += 1
            testCounter = 0
        
        # When both audios are played, do nothing more
        if audioCounter > 1:
            window['-STATUS_TEXT-'].update('Test completed! Congrats :)')
            continue
        
        time.sleep(2)
        
        # Update position
        PosManager = []
        for Obj in Objs:
            PosManager.append(GeomtryFunctions(Obj.SourcePosition, seq[testCounter][0], seq[testCounter][1]))
            
        # Re-Initialize FIR filter
        if seq[testCounter][2] == 'hrtf 1':    
            idxSOFA = 0
        elif seq[testCounter][2] == 'hrtf 2': 
            idxSOFA = 1
        idxPos = PosManager[idxSOFA].closestPosIdx(yaw=0, pitch=0, roll=0)
        FIRfilt = FIRfilter(method, buffer_sz, h=Objs[idxSOFA].Data_IR[idxPos, :, :].T)
        
        # Update audio
        audio_in, _ = sf.read(audioPath[audioCounter],
                              samplerate=None,
                              always_2d=True,
                              dtype=np.float32)  # input signal
        audio_in = np.mean(audio_in, axis=1, keepdims=True)
        N_ch = audio_in.shape[-1]
        
        # Clear stop_event
        stop_event.clear()
        
        # Update status
        window['-STATUS_TEXT-'].update('Test audio number: ' + str(testCounter) + ' audioCounter: ' + str(audioCounter))
        
        # Start new audio thread
        audio_thread = threading.Thread(target=rfx.start_audio,
                                        args=(fs, buffer_sz, audio_in,
                                              sofaIDXmanager, SOFAfiles,
                                              isHeadTracker, PosManager,
                                              HTreceiver, FIRfilt, Objs,
                                              stop_event, idxSOFA), daemon=False)
        audio_thread.start()

'''
Próximos passos:
    i) salvar quando a pessoa aperta o espaço
    ii) validar a posição na tela (para o operador ver)
    iii) salvar tudo de uma forma útil
'''
 



