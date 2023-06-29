# -*- coding: utf-8 -*-
"""
Created on Thu Jun 29 08:14:16 2023

@author: Felipe Ramos de Mello

Simple example of how to read a captured position result

"""

import numpy as np

a = np.load('subjects/felipe/pos_1.npz', allow_pickle=True)

print(a['posi'])
print(a['rightAnswer'])
