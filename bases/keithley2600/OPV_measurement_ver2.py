from keithley2600 import Keithley2600, ResultTable
import time
import numpy as np
import matplotlib.pyplot as plt
import pandas as pd
import os
from tkinter import filedialog
import serial
import bases.keithley2600.InstrumentsControl as InstrumentsControl


sample_name = "250908_CzDBA"
integration_time = 0.5 # ため込み時間(装置内?) /s
delay_time = 2 # 遅延時間1(装置内) /s
iteration = 5 # 遅延時間2(過渡電流モニター用)

filedir = filedialog.askdirectory(initialdir=os.path.dirname(os.path.abspath('__file__'))) # 保存フォルダの指定

#keithley2600 に接続
k = Keithley2600('USB0::0x05E6::0x2612::4043586::INSTR', visa_library="C:\\WINDOWS\\system32\\visa64.dll",timeout = None)
k.set_integration_time(k.smua, integration_time)

# 電圧のリスト生成
Vmin=-0.5
Vmax=2.2
vstep1=0.05

#port_a
Va0=np.arange(Vmin,Vmax+vstep1,vstep1)

Valist=[]

for j in range(len(Va0)):
    Valist_children=Va0[j]*np.ones(iteration)
    Valist = np.append(Valist, Valist_children)    

Valist=np.ravel(Valist) #電圧リストのndarrayに変換

print(Valist)


print("measurement time:",len(Valist)*(delay_time+integration_time)/60,"min") #測定時間の予測

V = []
I = []

k.smua.source.output = k.smua.OUTPUT_ON
k.smub.source.output = k.smub.OUTPUT_ON

#1点ごとに電圧を設定し、電流と輝度の測定
for voltage in Valist:
    k.smua.source.levelv = voltage       #電圧の設定
    k.smub.source.levelv = 0
    time.sleep(delay_time)         #delaytimeの設定
    print(voltage)
    current = -1*float(k.smub.measure.i())   #電流の測定
    print(current)
    V.append(voltage)
    I.append(current)

k.smua.source.output = k.smua.OUTPUT_OFF
k.smub.source.output = k.smub.OUTPUT_OFF


# データをDataFrameにまとめる
data = {'voltage [V]': V, 'current [A]': I}
df = pd.DataFrame(data)

# データをCSVファイルに保存
csv_filename = os.path.join(filedir, f"{sample_name}_OPV_measurement_data.csv")
df.to_csv(csv_filename, index=False)

print(f"saved to {csv_filename} ")

# データをプロット
fig = plt.figure()

ax1 = fig.add_subplot(1, 1, 1)
ax1.plot(V, I, color="red")
ax1.set_xlabel("voltage [V]")
ax1.set_ylabel("current [A]")
ax1.set_title("current vs voltage")


plt.tight_layout()
plt.show()