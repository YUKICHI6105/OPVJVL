from keithley2600 import Keithley2600, ResultTable
import time
import numpy as np
import matplotlib.pyplot as plt
import pandas as pd
import os
from tkinter import filedialog

sample_name = "002_spot3_1"
integration_time = 0.5 # ため込み時間(装置内?) /s
delay_time = 2 # 遅延時間1(装置内) /s

iteration = 4 # 遅延時間2(過渡電流モニター用)

filedir = filedialog.askdirectory(initialdir=os.path.dirname(os.path.abspath('__file__'))) # 保存フォルダの指定

k = Keithley2600('USB0::0x05E6::0x2612::4043586::INSTR', visa_library="C:\\WINDOWS\\system32\\visa64.dll")
k.set_integration_time(k.smua, integration_time)  # sets integration time in sec
k.set_integration_time(k.smub, integration_time)  # sets integration time in sec

# 電圧のリスト生成
Vmin=-0.1
Vmax=2.00
vstep1=0.03
Va0=np.arange(Vmin,Vmax+vstep1,vstep1)

Valist=[]

for j in range(len(Va0)):
    Valist_children=Va0[j]*np.ones(iteration)
    Valist = np.append(Valist, Valist_children)      # 本測定の電圧スイープ

Valist=np.ravel(Valist)

##########################################館農追加
# Valist = -50*np.ones(iteration)
# Vblist = -50*np.ones(iteration)
#########################################

# # 終了後にslow downさせるためのリスト(館農追加)
# Va_rst0 = np.arange(Vmax, 0, -Vstep)
# # Va_rst0 = np.zeros(10)
# Vb_rst0 = np.arange(Vb0, 0, -round(Vb0/len(Va_rst0),2))
# # Vb_rst0 = np.zeros(len(Va_rst0))
# Va_rst = np.append(Va_rst0, 0)
# Vb_rst = np.append(Vb_rst0, 0)
# while len(Va_rst)!=len(Vb_rst):
#     if len(Va_rst)>len(Vb_rst):
#         Vb_rst = np.append(Vb_rst, 0)
#     if len(Va_rst)<len(Vb_rst):
#         Va_rst = np.append(Va_rst, 0)

print(Valist)
# print(Vblist)
print(len(Valist)*(delay_time+integration_time)/60, "min")

    # fig = plt.figure()
    # ax1 = fig.add_subplot(1,2,1)
    # ax2 = fig.add_subplot(1,2,2)

#"""
for j in range(1):
    fig = plt.figure()
    ax1 = fig.add_subplot(1,2,1)
    ax2 = fig.add_subplot(1,2,2)   
    V,I = k.voltage_sweep_single_smu(k.smua, Valist.round(2), t_int=integration_time, delay=delay_time, pulsed=False)
    # Va,Ia, Vb,Ib = k.voltage_sweep_dual_smu(k.smua,k.smub, Valist, Vblist, t_int=integration_time, delay=delay_time, pulsed=False) # メイン実行部
    
    ax1.plot(V,I,marker="o", markersize=2)
    df = pd.DataFrame(
        data={"Va[V]": V, 
            "Ia[A]": I,
            }
    )
    filename = os.path.join(filedir,f"{sample_name}_{Vmin}to{-Vmax}_int{integration_time}s_delay{delay_time}s_{j+1}.csv")
    df.to_csv(filename)
    print(f"saved to {filename}")

    # slow down(館農追加)
    # rst1, rst2, rst3, rst4 = k.voltage_sweep_dual_smu(k.smua,k.smub, Va_rst, Vb_rst, t_int=integration_time, delay=1, pulsed=False)
    
    plt.show()
#"""
    
