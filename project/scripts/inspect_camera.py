import cv2

def inspect_camera():
    cap = cv2.VideoCapture(0)

    if not cap.isOpened():
        print("No se pudo abrir la cámara.")
        return

    print("Resolución actual:")
    print("Width:", cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    print("Height:", cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    print("FPS:", cap.get(cv2.CAP_PROP_FPS))

    print("\nIntentando establecer 1920x1080...")

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)

    print("Resolución después de set:")
    print("Width:", cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    print("Height:", cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    print("\nPropiedades de foco:")
    print("AutoFocus:", cap.get(cv2.CAP_PROP_AUTOFOCUS))
    print("Focus value:", cap.get(cv2.CAP_PROP_FOCUS))

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        cv2.imshow("Camera Test", frame)

        if cv2.waitKey(1) & 0xFF == 27:
            break

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    inspect_camera()