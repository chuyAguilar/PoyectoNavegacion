import pyigtl
import numpy as np
import time

client = pyigtl.OpenIGTLinkClient("127.0.0.1", 18944)

t = 0

while True:

    T = np.eye(4)
    T[0,3] = np.sin(t) * 50

    msg = pyigtl.TransformMessage(
        device_name="Pointer",
        matrix=T
    )

    client.send_message(msg)

    t += 0.05
    time.sleep(0.05)