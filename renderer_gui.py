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
         sg.OptionMenu(values=sofa_files, default_value='Individualized HRTF', key="-HRTF_1-", size=(20,20), pad=(5,20)),
         sg.OptionMenu(values=sofa_files, default_value='Generic HRTF', key="-HRTF_2-", size=(20,20), pad=(5,20)),
        ],
        
        [sg.Button('Setup', size=(10,2), font=font, button_color="orange", pad=(20,20)),
         sg.Button('Start', size=(10,2), font=font, button_color="green", pad=(20, 20), disabled=True, key='-START-')],
        
        [sg.Text('Wating for setup...', key='-STATUS_TEXT-', font=("OpenSans", 20), justification='center', pad=(0, 20))],
        
        [sg.Text('', key='-STATUS_TEXT_2-', font=("OpenSans", 20), justification='center', pad=(0, 20))],
        
        [sg.Button('Next audio', key='-NEXT-', size=(25,2), font=font, disabled=True, pad=(0, 20))],
        
        [sg.Text('', key='-TEST_SEQ-', font=("OpenSans", 20), justification='center', pad=(0,20))],
        
        [sg.Text('', key='-TEST_NUM-', font=("OpenSans", 20), justification='center', pad=(0,20))]
        
    ]


# Initialize headtracker
if isHeadTracker:
    thread = threading.Thread(target=HeadTracker.start, args=(CAM_ID, HT_PORT), daemon=False)  # track listener position
    thread.start()
    # HTreceiver = PositionReceiver(save_path, IP=HT_IP, PORT=HT_PORT)  # read head tracker position data

time.sleep(2)

window = sg.Window('multiHRTFrenderer', layout, element_justification='c',
                   font=font, return_keyboard_events=True, size=(900, 800))

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
        
        # Azimuth and elevation for audio 1
        az1 = [30, 0]
        el1 = [30, 70]
        
        # Azimuth and elevation for audio 2
        az2 = [-40, -20]
        el2 = [-70, 60]
        
        hrtf = ['HRTF: Individualized', 'HRTF: Generic']
        
        # Set a random test sequence
        seq1 = []
        seq2 = []
        seq = []
        
        for ii in range(len(az1)):
            seq1.append([az1[ii], el1[ii], hrtf[0]])
            seq1.append([az1[ii], el1[ii], hrtf[1]])
        
        for ii in range(len(az2)):
            seq2.append([az2[ii], el2[ii], hrtf[0]])
            seq2.append([az2[ii], el2[ii], hrtf[1]])
        
        random.shuffle(seq1)
        random.shuffle(seq2)
        
        seq.extend(seq1)
        seq.extend(seq2)
        
        testNum = len(seq)
        
        # Set the audio file to be played
        testCounter = 0
        audioCounter = 0
        saveCount = 1
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
        
        # convert positions to navigational coordinates for ease to use
        def sph2cart(posArray):
            idx = np.where(posArray[:, 0] > 180)[0]
            posArray[idx, 0] = posArray[idx, 0] - 360
            return posArray

        for n in range(len(Objs)):
            Objs[n].SourcePosition = sph2cart(Objs[n].SourcePosition)
        
        # Audio input
        audio_in, _ = sf.read(audioPath[0],
                              samplerate=None,
                              always_2d=True,
                              dtype=np.float32)  # input signal
        audio_in = np.mean(audio_in, axis=1, keepdims=True)
        N_ch = audio_in.shape[-1]
        
        # initialize position index manager
        PosManager = []
        for Obj in Objs:
            PosManager.append(GeomtryFunctions(Obj.SourcePosition, seq[testCounter][0], seq[testCounter][1]))
            
        # Initialize FIR filter
        if seq[testCounter][2] == 'HRTF: Individualized':    
            idxSOFA = 0
        elif seq[testCounter][2] == 'HRTF: Generic': 
            idxSOFA = 1
        idxPos = PosManager[idxSOFA].closestPosIdx(yaw=0, pitch=0, roll=0)
        FIRfilt = FIRfilter(method, buffer_sz, h=Objs[idxSOFA].Data_IR[idxPos, :, :].T)
        
        # Stop event for the audio thread
        stop_event = threading.Event()
        
        time.sleep(1)
        window['-START-'].update(disabled=False)
        window['-STATUS_TEXT-'].update('Setup complete! Click Start to begin the test.')
        
        
#################################################################################################
#################################################################################################

    # Start the test
    if event=='-START-':
        
        window['-NEXT-'].update(disabled=False)
        
        statusStr = ['Audio File: ' + audioPath[audioCounter][6:] + '  ' +
                     'Azimuth: ' + str(seq[testCounter][0]) + '  ' +
                     'Elevation: ' + str(seq[testCounter][1])]
        
        statusStr2 = str(seq[testCounter][2])
        
        window['-STATUS_TEXT-'].update(statusStr)
        window['-STATUS_TEXT_2-'].update(statusStr2)
        
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
        
        HTreceiver.rightAnswer = seq[testCounter]
        window['-TEST_SEQ-'].update('Waiting for the subject´s response...')
        window['-TEST_NUM-'].update('Test [' + str(testCounter + 1) + '/' + str(testNum) + ']')
        
##################################################################################################
##################################################################################################

    if event=='-NEXT-':
        
        # Stop last audio
        stop_event.set()
        testCounter += 1
        
        # Activate next audio
        if testCounter >= len(seq1):
            audioCounter = 1
        
        # When both audios are played, do nothing more
        if testCounter >= len(seq):
            window['-STATUS_TEXT-'].update('Test completed! Congrats :)')
            window['-STATUS_TEXT_2-'].update('')
            window['-TEST_SEQ-'].update('')
            continue
        
        
        # Save the right answer for validation
        HTreceiver.rightAnswer = seq[testCounter]
        
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
        
        # Update the display
        statusStr = ['Audio File: ' + audioPath[audioCounter][6:] + '  ' +
                     'Azimuth: ' + str(seq[testCounter][0]) + '  ' +
                     'Elevation: ' + str(seq[testCounter][1])]
        
        statusStr2 = str(seq[testCounter][2])
        
        window['-STATUS_TEXT-'].update(statusStr)
        window['-STATUS_TEXT_2-'].update(statusStr2)
        window['-TEST_SEQ-'].update('Waiting for the subject´s response...')
        window['-TEST_NUM-'].update('Test [' + str(testCounter + 1) + '/' + str(testNum) + ']')
        
        
        # Start new audio thread
        audio_thread = threading.Thread(target=rfx.start_audio,
                                        args=(fs, buffer_sz, audio_in,
                                              sofaIDXmanager, SOFAfiles,
                                              isHeadTracker, PosManager,
                                              HTreceiver, FIRfilt, Objs,
                                              stop_event, idxSOFA), daemon=False)
        audio_thread.start()

################################################################################
     
    if event == 'Right:39':
        window['-TEST_SEQ-'].update('The subject has pressed the button!')

'''
Próximos passos:
    i) salvar quando a pessoa aperta o espaço
    ii) validar a posição na tela (para o operador ver)
    iii) adicionar no save qual HRTF foi utilizada e qual áudio tbm
'''
 



