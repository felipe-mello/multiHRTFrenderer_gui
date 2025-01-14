# %% import libs
import os
import time
import socket
import threading
import numpy as np

'''
FELIPE: added a "user_save_path" variable for the captured positions
'''
class PositionReceiver():
    def __init__(self, user_save_path, IP='0.0.0.0', PORT=5555):
        self.sock = socket.socket(socket.AF_INET,  # Internet
                                  socket.SOCK_DGRAM)  # UDP
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind((IP, PORT))
        self.yaw = 0
        self.pitch = 0
        self.roll = 0
        self.x = 0
        self.y = 1
        self.z = 1
        self.rightAnswer = []

        # create path to store position when requested
        self.save_path = os.path.join(os.getcwd(), user_save_path) # Changed by Felipe
        if not os.path.isdir(self.save_path):
            os.makedirs(self.save_path)

        self.t = threading.Thread(target=self.reader, daemon=True).start()
        
    '''
    FELIPE: adicionei esse rightAnswer, que corresponde aos ângulos de azimute e elevação
    pré-definidos para os testes. Assim é possível comparar a posição marcada pelo sujeito
    com a que foi de fato reproduzida.
    '''
    def reader(self):
        print('position receiver initialized')
        idx_save = 0
        while True:
            data, addr = self.sock.recvfrom(1024)
            if len(data) > 0:
                tmp = data.decode()
                if 'captur' in tmp.lower():  # save .npz with the latest position
                    idx_save += 1
                    fullpath = os.path.join(self.save_path, f'pos_{idx_save}')
                    position = {'x': self.x,
                                'y': self.y,
                                'z': self.z,
                                'yaw': self.yaw,
                                'pitch': self.pitch,
                                'roll': self.roll
                                }
                    rightAns = {'rightAnswer': self.rightAnswer} # A resposta certa de acordo com a posição pré-selecionada da fonte
                    np.savez(fullpath, posi=position, rightAnswer=rightAns, time=time.localtime())
                    print(f'Saved position {idx_save}')
                else:  # store the receive position
                    self.latest = data.decode()
                    self.str2pos()
            # time.sleep(0.2)

    def str2pos(self):
        splitStr = self.latest.split(',')
        yaw = float(splitStr[0])
        self.yaw = yaw
        self.pitch = float(splitStr[1])
        self.roll = float(splitStr[2])
        self.x = float(splitStr[3])
        self.y = float(splitStr[4])
        self.z = float(splitStr[5])
        
    def __del__(self):
      print ("Position Manager deleted!");

if __name__ == '__main__':
    a = PositionReceiver()
# %%
