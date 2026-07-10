import time
import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from tkinter import filedialog
import keithley2600.InstrumentsControl as InstrumentsControl

Keithley2400 = InstrumentsControl.Keithley2400("COM5")
BM9 = InstrumentsControl.BM9("COM4")

sample_name = "20260602_MAPbI3_p-pyrrd-phen_PM6Y6_3"
integration_time = 0.5 # ため込み時間(装置内?) /s
delay_time = 1 # 遅延時間1(装置内) /s
iteration = 3 # 遅延時間2(過渡電流モニター用)

filedir = filedialog.askdirectory(initialdir=os.path.dirname(os.path.abspath('__file__'))) # 保存フォルダの指定

Keithley2400.reset()
Keithley2400.clear_status()

Keithley2400.configure_source_voltage(compliance_current=0.02, nplc=1.0, auto_range=True)

# ==== 電圧リスト生成 ====
Vmin = -1.0
Vmax = 1.9
Vstep = 0.1

Voltage = np.arange(Vmin, Vmax + Vstep, Vstep)

Vlist = np.array([], dtype=float)
for v in Voltage:
    Vlist = np.append(Vlist, v * np.ones(iteration))

Vlist = np.ravel(Vlist)

print("Voltage list:", Vlist)
print("measurement time:", len(Vlist) * (delay_time + integration_time) / 60, "min")

V = []
I = []
L = []

print("Start JVL measurement")

try:
    Keithley2400.output_on()

    for v in Vlist:
        Keithley2400.set_voltage(v)
        time.sleep(delay_time)

        current = Keithley2400.measure_current()

        luminance = BM9.get_luminance()*100

        print(f"V = {v:.3f} V, I = {current:.3e} A, L = {luminance:.2f} cd/m^2")

        V.append(v)
        I.append(current)
        L.append(luminance)

finally:
    Keithley2400.output_off()
    Keithley2400.close()
    BM9.close()

data = {"voltage [V]": V, "current [A]": I, "luminance [cd/m2]": L}
df = pd.DataFrame(data)

csv_filename = os.path.join(filedir, f"{sample_name}_measurement_data.csv")
df.to_csv(csv_filename, index=False, encoding="utf-8")
print(f"Saved to {csv_filename}")

fig = plt.figure()

I_abs = np.abs(I)
L_abs = np.abs(L)

ax1 = fig.add_subplot(1, 2, 1)
ax1.plot(V, I_abs, marker="o", color="r", linestyle="None")
ax1.set_xlabel("Voltage [V]")
ax1.set_ylabel("Current [A]")
ax1.set_title("I-V")
ax1.set_yscale("log")

ax2 = fig.add_subplot(1, 2, 2)
ax2.plot(V, L_abs, marker="o", color="b", linestyle="None")
ax2.set_xlabel("Voltage [V]")
ax2.set_ylabel("Luminance [cd/m²]")
ax2.set_title("L-V")
ax2.set_yscale("log")

plt.tight_layout()
plt.show()