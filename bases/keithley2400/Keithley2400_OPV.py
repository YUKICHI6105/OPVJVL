import time
import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from tkinter import filedialog
import bases.keithley2600.InstrumentsControl as InstrumentsControl

Keithley2400 = InstrumentsControl.Keithley2400("COM5")

sample_name = "20260602_MAPbI3_p-pyrrd-phen_PM6Y6_2"
integration_time = 0.5 # ため込み時間(装置内?) /s
delay_time = 1 # 遅延時間1(装置内) /s
iteration = 3 # 遅延時間2(過渡電流モニター用)

filedir = filedialog.askdirectory(initialdir=os.path.dirname(os.path.abspath('__file__'))) # 保存フォルダの指定

Keithley2400.reset()
Keithley2400.clear_status()

Keithley2400.configure_source_voltage(compliance_current=0.02, nplc=1.0, auto_range=True)

# ==== 電圧リスト生成 ====
Vmin = -0.1
Vmax = 1.1
Vstep = 0.02

Voltage = np.arange(Vmin, Vmax + Vstep, Vstep)

Vlist = np.array([], dtype=float)
for v in Voltage:
    Vlist = np.append(Vlist, v * np.ones(iteration))

Vlist = np.ravel(Vlist)

print("Voltage list:", Vlist)
print("measurement time:", len(Vlist) * (delay_time + integration_time) / 60, "min")

V = []
I = []

print("Start OPV measurement")

try:
    Keithley2400.output_on()

    for v in Vlist:
        Keithley2400.set_voltage(v)
        time.sleep(delay_time)

        current = Keithley2400.measure_current()

        print(f"V = {v:.3f} V, I = {current:.3e} A")

        V.append(v)
        I.append(current)

finally:
    Keithley2400.output_off()
    Keithley2400.close()

data = {"voltage [V]": V, "current [A]": I}
df = pd.DataFrame(data)

csv_filename = os.path.join(filedir, f"{sample_name}_OPV_measurement_data.csv")
df.to_csv(csv_filename, index=False, encoding="utf-8")
print(f"Saved to {csv_filename}")

fig = plt.figure()



ax = fig.add_subplot(1, 1, 1)
ax.plot(V, I, marker="o", color="r", linestyle="None")
ax.set_xlabel("Voltage [V]")
ax.set_ylabel("Current [A]")
ax.set_title("I-V")

plt.tight_layout()
plt.show()