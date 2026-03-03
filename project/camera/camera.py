import cv2


class Camera:
    def __init__(self, index=0, width=1920, height=1080):
        self.cap = cv2.VideoCapture(index, cv2.CAP_DSHOW)

        if not self.cap.isOpened():
            raise RuntimeError("No se pudo abrir la cámara.")

        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)

        self.width = width
        self.height = height

    def read(self):
        ret, frame = self.cap.read()
        if not ret:
            raise RuntimeError("No se pudo leer frame.")
        return frame

    def release(self):
        self.cap.release()
        cv2.destroyAllWindows()