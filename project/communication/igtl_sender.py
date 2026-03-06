import pyigtl
import numpy as np


class IGTLSender:

    def __init__(self, host="127.0.0.1", port=18944):
        self.client = pyigtl.OpenIGTLinkClient(host, port)

    def send_transform(self, name, matrix):
        """
        matrix: 4x4 numpy transform
        """
        msg = pyigtl.TransformMessage(
            device_name=name,
            matrix=matrix
        )

        self.client.send_message(msg)