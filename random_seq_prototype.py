# -*- coding: utf-8 -*-
"""
Created on Mon Jun 26 17:33:11 2023

@author: felip
"""

import random

az = [30, 0, -45]
el = [30, 70, -45]
hrtf = ['hrtf 1', 'hrtf 2']
seq = []

for ii in range(len(az)):
    seq.append([az[ii], el[ii], hrtf[0]])
    
for ii in range(len(az)):
    seq.append([az[ii], el[ii], hrtf[1]])
    
random.shuffle(seq)