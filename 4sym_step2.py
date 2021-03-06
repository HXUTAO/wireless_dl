import torch
import torch.nn as nn
import numpy as np
from torch import optim
import torch.nn.functional as F
import random as rn
import matplotlib.pyplot as plt
from noise import Noise_1
import os
import system
import argparse

parser = argparse.ArgumentParser()
parser.add_argument('--num_channels', type=int,default=2)
parser.add_argument('--no_epochs', type=int,default=100)
parser.add_argument('--batch_size', type=int,default=100)
parser.add_argument('--lr', type=float,default=0.0001)
parser.add_argument('--hidden_neurons', type=int,default=50)
data = parser.parse_args()

from system import comm_4_2
from transmitter import transmitter_4
from receiver import receiver_4
device = "cuda" if torch.cuda.is_available() else "cpu"

domain = [4,16,64]
N_symbols = 4
if N_symbols not in domain: raise ValueError('Not the correct number of symbols')
bits = np.log2(N_symbols)
bits = int(bits)
print('No. of possible symbols are {}. Each symbol requires {} bits'.format(N_symbols, bits))
hidden_neurons =data.hidden_neurons

N = 10000
num_channels = data.num_channels
rate = bits/num_channels

no_epochs = data.no_epochs
batch_size = data.batch_size

com_system = comm_4_2(N_symbols, num_channels, rate, batch_size, hidden_neurons=hidden_neurons)
com_system = com_system.to(device)
optimizer = optim.Adam(com_system.parameters(), lr = data.lr)
criterion = nn.CrossEntropyLoss()
na = 'step1_4sym_final.pth'
com_system.load_state_dict(torch.load(os.path.join(os.getcwd(),'files', na))['model'])
print('Loaded the model form previous step')

trans = transmitter_4(N_symbols, num_channels, hidden_neurons=hidden_neurons)
trans = trans.to(device)
recv = receiver_4(N_symbols, num_channels, hidden_neurons=hidden_neurons)
recv = recv.to(device)


for epoch in range(no_epochs):
    label = np.random.randint(N_symbols, size = N)

    inp = torch.zeros(N, N_symbols)
    for i,k in enumerate(label):
        inp[i][k] = 1

    inp = inp.to(device)
    label = torch.from_numpy(label)
    label = label.to(device)
    run_loss = []
    for j in range(0,N-batch_size, batch_size):
        loss = 0
        optimizer.zero_grad()
        ex = inp[j:j+batch_size]
        lab = label[j:j+batch_size]
        out = com_system(ex)
        loss = criterion(out, lab)
        run_loss.append(loss.item())
        loss.backward()
        optimizer.step()

    if ((epoch % 15) == 0):
        na = 'step2_{}_{}_4sym_epoch_{}.pth'.format(num_channels, bits, epoch)
        torch.save({'model':com_system.state_dict(), 'opt':optimizer.state_dict()}, os.path.join(os.getcwd(),'files', na))
    print('Loss for the epoch {} is {}'.format(epoch+1, sum(run_loss)/len(run_loss)))
    run_loss = []

trans.load_state(com_system.lin1, com_system.lin2,com_system.lin3, com_system.lin_c, com_system.norm1)
recv.load_state(com_system.lin4, com_system.lin5, com_system.lin6)
na = 'step2_4sym_final.pth'
torch.save({'model':com_system.state_dict(), 'opt':optimizer.state_dict()}, os.path.join(os.getcwd(),'files', na))
test_N = 100000
test_label = np.random.randint(N_symbols, size = test_N)

inp_test = torch.zeros(test_N, N_symbols)
for i,k in enumerate(test_label):
    inp_test[i][k] = 1
inp_test = inp_test.to(device)
test_label = torch.from_numpy(test_label)
test_label = test_label.to(device)

def gen(x,y,step):
    while x<y:
        yield round(x,2)
        x += step

#calculating for various snr
Ebno_range_snr = list(gen(-5,10,0.5))
ber = [None] * len(Ebno_range_snr)
for k in range(len(Ebno_range_snr)):
    Ebno=10.0**(Ebno_range_snr[k]/10.0)  #conversion of dB to normal value
    noise_mean = 0
    noise_std = np.sqrt(1/(2*Ebno * rate))
    noise_layer = Noise_1((test_N, num_channels * 2), std = noise_std)

    no_error = 0
    #noise = torch.randn(test_N, 2*num_channels) * noise_std
    #noise = noise.to(device)
    trans_out = trans(inp_test)
    #print(trans_out)
    #print('-----------------------------------------------------')
    noise = noise_layer(trans_out)
    noise_out =  noise
    recv_out = recv(noise_out)
    #print(recv_out)
    _, pred_out = torch.max(recv_out, dim=1)
    no_error = pred_out != test_label
    no_error = torch.sum(no_error).item()
    ber[k] = no_error/test_N
    print('SNR->{} BER->{}'.format(Ebno_range_snr[k], ber[k]))

name = 'S2_4S_Autoencoder({},{})_comp'.format(num_channels, bits)
plt.plot(Ebno_range_snr, ber, 'y',label=name)
plt.yscale('log')
plt.xlabel('SNR Range')
plt.ylabel('Block Error Rate')
plt.grid()
plt.legend(loc='upper right')
plt.savefig(os.path.join(os.getcwd(),'files', name))
plt.show()
