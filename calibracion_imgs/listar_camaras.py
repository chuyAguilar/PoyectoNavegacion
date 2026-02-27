import cv2

def list_ports():
    """
    Test the ports and returns a tuple with the available ports and the ones that are working.
    """
    non_working_ports = []
    dev_port = 0
    working_ports = []
    available_ports = []
    while len(non_working_ports) < 6: # if there are more than 5 non working ports stop the testing. 
        camera = cv2.VideoCapture(dev_port, cv2.CAP_DSHOW)
        if not camera.isOpened():
            non_working_ports.append(dev_port)
            print(f"Port {dev_port} is not working.")
        else:
            is_reading, img = camera.read()
            w = camera.get(3)
            h = camera.get(4)
            if is_reading:
                print(f"Port {dev_port} is working and reads images ({w}x{h})")
                working_ports.append(dev_port)
            else:
                print(f"Port {dev_port} for camera ( {w}x{h}) is present but does not reads.")
                available_ports.append(dev_port)
        dev_port +=1
    return available_ports,working_ports,non_working_ports

print("Buscando cámaras disponibles...")
list_ports()
