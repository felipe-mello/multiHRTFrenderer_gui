# -*- coding: utf-8 -*-
"""
Created on Mon Jun 26 15:39:16 2023

@author: felip
"""

import os
import PySimpleGUI as sg

sofa_files = os.listdir('SOFA/')
audio_files = os.listdir('Audio/')

selected_audio = audio_files[0]
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
    
    if event=="-AUDIO_FILE-":
        selected_audio = values['-AUDIO_FILE-']
        print(selected_audio)
    
    if event=='Select SOFA':
        print(values['-SOFA_FILE-'])
        
    if event=='Select Audio':
        print(values['-AUDIO_FILE-'])
    
    if event=='Exit':
        window.close()
        break

    if window.is_closed():
        break
    